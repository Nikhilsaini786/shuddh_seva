from flask import Flask, render_template, request, jsonify, redirect, url_for, session, send_file
import json
from pathlib import Path
import os
import io
import csv
from datetime import datetime
import database as db

app = Flask(__name__)
app.secret_key = os.urandom(24)
BASE_DIR = Path(__file__).resolve().parent

# Ensure database is initialized
db.init_db()

def load_products():
    with open(BASE_DIR / "products.json", encoding="utf-8") as file:
        return json.load(file)

def get_current_user():
    user_id = session.get("user_id")
    if user_id:
        return db.get_user_by_id(user_id)
    return None

@app.route("/")
def home():
    products = load_products()
    current_user = get_current_user()
    return render_template("index.html", products=products, current_user=current_user)

@app.route("/api/products")
def api_products():
    return jsonify(load_products())

@app.route("/login")
@app.route("/signup")
def auth_page():
    if session.get("user_id"):
        return redirect(url_for("home"))
    return render_template("auth.html")

# ----------------- CUSTOMER OTP VERIFICATION & AUTHENTICATION ----------------- #

@app.route("/api/auth/send-otp", methods=["POST"])
def auth_send_otp():
    try:
        data = request.get_json(force=True)
        phone = (data.get("phone") or "").strip()
        
        # Clean phone to 10 digits
        phone = "".join(filter(str.isdigit, phone))
        if len(phone) > 10 and phone.startswith("91"):
            phone = phone[-10:]
            
        if len(phone) != 10:
            return jsonify({"success": False, "error": "Please enter a valid 10-digit mobile number."}), 400

        otp_code, is_existing, user_data = db.create_otp(phone)

        return jsonify({
            "success": True,
            "phone": phone,
            "is_existing": is_existing,
            "user_name": user_data["name"] if user_data else "",
            "message": f"OTP successfully sent to +91 {phone}",
            "otp_code": otp_code  # For instant on-screen display & testing
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/auth/verify-otp", methods=["POST"])
def auth_verify_otp():
    try:
        data = request.get_json(force=True)
        phone = (data.get("phone") or "").strip()
        otp_code = (data.get("otp_code") or "").strip()
        name = (data.get("name") or "").strip()
        address = (data.get("address") or "").strip()
        landmark = (data.get("landmark") or "").strip()
        city = (data.get("city") or "Jaipur").strip()
        state = (data.get("state") or "Rajasthan").strip()
        pincode = (data.get("pincode") or "").strip()

        phone = "".join(filter(str.isdigit, phone))
        if len(phone) > 10 and phone.startswith("91"):
            phone = phone[-10:]

        if not phone or not otp_code:
            return jsonify({"success": False, "error": "Mobile number and OTP are required."}), 400

        verified, existing_user = db.verify_otp_code(phone, otp_code)
        if not verified:
            return jsonify({"success": False, "error": "Invalid OTP code. Please enter the correct 4-digit OTP."}), 400

        # If user does not exist yet, name is required
        if not existing_user and not name:
            return jsonify({
                "success": False,
                "needs_name": True,
                "error": "Please enter your full name to complete signup."
            }), 400

        user = db.get_or_create_user_otp(phone, name, address, landmark, city, state, pincode)

        # Set customer session
        session["user_id"] = user["id"]
        session["user_name"] = user["name"]
        session["user_phone"] = user["phone"]

        return jsonify({
            "success": True,
            "message": f"Welcome, {user['name']}!",
            "user": user
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/auth/logout", methods=["POST", "GET"])
def auth_logout():
    session.pop("user_id", None)
    session.pop("user_name", None)
    session.pop("user_phone", None)
    return jsonify({"success": True, "message": "Logged out successfully."})

@app.route("/api/auth/me", methods=["GET"])
def auth_me():
    user = get_current_user()
    if user:
        return jsonify({"logged_in": True, "user": user})
    return jsonify({"logged_in": False})

@app.route("/api/user/orders", methods=["GET"])
def user_orders():
    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
    orders = db.get_user_orders(user["id"])
    return jsonify({"success": True, "orders": orders})

# ----------------- ORDER PLACEMENT (MANDATORY OTP AUTH) ----------------- #

@app.route("/api/order", methods=["POST"])
def place_order():
    try:
        user_id = session.get("user_id")
        if not user_id:
            return jsonify({
                "success": False,
                "requires_auth": True,
                "error": "Order karne ke liye Mobile OTP verification jaruri hai."
            }), 401
        
        data = request.get_json(force=True)
        if not data or not data.get("items") or not data.get("name") or not data.get("phone"):
            return jsonify({"success": False, "error": "Missing required order information."}), 400
        
        saved_order = db.save_order(data, user_id=user_id)
        
        items_summary = "\n".join([
            f"• {item.get('name')} ({item.get('size')}g) × {item.get('qty')} = ₹{int(item.get('price', 0)) * int(item.get('qty', 1))}"
            for item in saved_order.get("items", [])
        ])
        
        wa_message = (
            f"🛒 *NEW ORDER: #{saved_order['order_id']}*\n"
            f"---------------------------------\n"
            f"👤 *Customer:* {saved_order['customer_name']}\n"
            f"📞 *Phone:* {saved_order['phone']}\n"
            f"📍 *Address:* {saved_order['address']}, {saved_order['city']}, {saved_order['state']} - {saved_order['pincode']}\n"
            f"---------------------------------\n"
            f"*ITEMS ORDERED:*\n{items_summary}\n"
            f"---------------------------------\n"
            f"💰 *Total Amount:* ₹{int(saved_order['total_amount'])}\n"
            f"💳 *Payment Mode:* {saved_order['payment_method']}\n"
            f"---------------------------------\n"
            f"🙏 Thank you for choosing Shuddh Seva Foods!"
        )
        
        admin_phone = db.get_setting("admin_phone", "6350474290")
        
        return jsonify({
            "success": True,
            "order": saved_order,
            "whatsapp_message": wa_message,
            "admin_phone": admin_phone
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/track", methods=["GET", "POST"])
def track_order():
    query = request.args.get("query", "").strip() or (request.json.get("query", "").strip() if request.is_json else "")
    if not query:
        return jsonify({"success": False, "error": "Please provide Order ID or Phone Number."}), 400
    
    order = db.get_order_by_id(query)
    if order:
        return jsonify({"success": True, "order": order})
    return jsonify({"success": False, "error": f"No order found matching '{query}'. Please check and try again."}), 404

@app.route("/api/inquiry", methods=["POST"])
def submit_inquiry():
    try:
        data = request.get_json(force=True)
        if not data.get("name") or not data.get("phone") or not data.get("message"):
            return jsonify({"success": False, "error": "Name, phone and message are required."}), 400
        
        db.save_inquiry(data)
        return jsonify({"success": True, "message": "Inquiry submitted successfully! Our team will contact you shortly."})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# ----------------- STRICT ADMIN CONTROL ROUTES (CUSTOMERS BLOCKED) ----------------- #

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        data = request.get_json(silent=True) or request.form
        password = data.get("password", "")
        correct_password = db.get_setting("admin_password", "shuddh123")
        
        if password == correct_password:
            session["admin_logged_in"] = True
            if request.is_json:
                return jsonify({"success": True})
            return redirect(url_for("admin_dashboard"))
        else:
            if request.is_json:
                return jsonify({"success": False, "error": "Incorrect password"}), 401
            return render_template("admin_login.html", error="Invalid admin passcode. Default is shuddh123")
            
    if session.get("admin_logged_in"):
        return redirect(url_for("admin_dashboard"))
    return render_template("admin_login.html")

@app.route("/admin/logout")
def admin_logout():
    session.pop("admin_logged_in", None)
    return redirect(url_for("admin_login"))

@app.route("/admin")
def admin_dashboard():
    # Only Admin can enter - customers strictly blocked!
    if not session.get("admin_logged_in"):
        return redirect(url_for("admin_login"))
    return render_template("admin.html")

@app.route("/api/admin/orders")
def api_admin_orders():
    if not session.get("admin_logged_in"):
        return jsonify({"error": "Unauthorized access. Only Admin allowed."}), 401
    
    status_filter = request.args.get("status", "all")
    search = request.args.get("search", "")
    orders = db.get_orders(limit=200, status_filter=status_filter, search=search)
    return jsonify(orders)

@app.route("/api/admin/order/<order_id>/status", methods=["POST"])
def api_update_order_status(order_id):
    if not session.get("admin_logged_in"):
        return jsonify({"error": "Unauthorized access. Only Admin allowed."}), 401
    
    data = request.get_json(force=True)
    new_status = data.get("order_status")
    payment_status = data.get("payment_status")
    
    if not new_status:
        return jsonify({"error": "Status is required"}), 400
        
    db.update_order_status(order_id, new_status, payment_status)
    return jsonify({"success": True, "order_id": order_id, "new_status": new_status})

@app.route("/api/admin/stats")
def api_admin_stats():
    if not session.get("admin_logged_in"):
        return jsonify({"error": "Unauthorized access. Only Admin allowed."}), 401
    return jsonify(db.get_stats())

@app.route("/api/admin/inquiries")
def api_admin_inquiries():
    if not session.get("admin_logged_in"):
        return jsonify({"error": "Unauthorized access. Only Admin allowed."}), 401
    return jsonify(db.get_inquiries())

@app.route("/admin/invoice/<order_id>")
def admin_invoice(order_id):
    # Printable bill can be accessed with admin session or by the customer who owns the order
    order = db.get_order_by_id(order_id)
    if not order:
        return "Order not found", 404
        
    is_admin = bool(session.get("admin_logged_in"))
    is_owner = bool(session.get("user_id") and order.get("user_id") == session.get("user_id"))
    
    if not is_admin and not is_owner:
        return redirect(url_for("admin_login"))
        
    return render_template("invoice.html", order=order, items=order.get("items", []))

@app.route("/api/admin/export-orders")
def export_orders():
    if not session.get("admin_logged_in"):
        return jsonify({"error": "Unauthorized access. Only Admin allowed."}), 401
    
    orders = db.get_orders(limit=1000)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Order ID", "Date", "Customer Name", "Phone", "WhatsApp", "Email",
        "Address", "City", "State", "Pincode", "Items", "Subtotal",
        "Discount", "Delivery Fee", "Total", "Payment Method", "Payment Status", "Order Status"
    ])
    for o in orders:
        items_str = "; ".join([f"{i.get('name')} {i.get('size')}g x{i.get('qty')}" for i in o.get("items", [])])
        writer.writerow([
            o["order_id"], o["created_at"], o["customer_name"], o["phone"], o["whatsapp"], o["email"],
            o["address"], o["city"], o["state"], o["pincode"], items_str, o["subtotal"],
            o["discount"], o["delivery_fee"], o["total_amount"], o["payment_method"], o["payment_status"], o["order_status"]
        ])
    
    output.seek(0)
    return send_file(
        io.BytesIO(output.getvalue().encode("utf-8")),
        mimetype="text/csv",
        as_attachment=True,
        download_name=f"shuddh_seva_orders_{datetime.now().strftime('%Y%m%d')}.csv"
    )

if __name__ == "__main__":
    app.run(debug=True, port=5006)
