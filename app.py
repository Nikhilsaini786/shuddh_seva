from flask import Flask, render_template, request, jsonify, redirect, url_for, session, send_file
import json
from pathlib import Path
import os
import io
import csv
from datetime import datetime
from dotenv import load_dotenv

# Load environment configuration
load_dotenv()

import database as db
from services.otp_service import send_sms_otp, send_email_otp

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY") or os.urandom(24)
BASE_DIR = Path(__file__).resolve().parent

# Ensure database and seed data are initialized
db.init_db()

def mask_target(target: str, target_type: str = "phone") -> str:
    """Mask target for secure display (e.g., +91 ******4290 or in***@gmail.com)."""
    target = str(target).strip()
    if target_type == "phone":
        clean = "".join(filter(str.isdigit, target))
        if len(clean) >= 10:
            return f"+91 ******{clean[-4:]}"
        return target
    else:
        if "@" in target:
            parts = target.split("@")
            user_part = parts[0]
            masked_user = user_part[:2] + "***" if len(user_part) > 2 else user_part + "***"
            return f"{masked_user}@{parts[1]}"
        return target

def get_current_user():
    user_id = session.get("user_id")
    if user_id:
        return db.get_user_by_id(user_id)
    return None

def get_current_admin():
    if session.get("admin_logged_in"):
        return session.get("admin_user") or db.get_admin_user()
    return None

# ----------------- PUBLIC STORE ROUTES ----------------- #

@app.route("/")
def home():
    products = db.get_all_products(active_only=False)
    current_user = get_current_user()
    return render_template("index.html", products=products, current_user=current_user)

@app.route("/api/products")
def api_products():
    return jsonify(db.get_all_products(active_only=False))

@app.route("/login")
@app.route("/signup")
def auth_page():
    if session.get("user_id"):
        return redirect(url_for("home"))
    return render_template("auth.html")

# ----------------- CUSTOMER OTP AUTHENTICATION (MOBILE & EMAIL) ----------------- #

@app.route("/api/auth/send-otp", methods=["POST"])
def auth_send_otp():
    """
    Generate and deliver a real 6-digit OTP via Twilio SMS or Gmail SMTP.
    Does NOT return the OTP code to the frontend!
    """
    try:
        data = request.get_json(force=True) if request.is_json else request.form
        auth_type = data.get("type", "phone").lower().strip()
        target = data.get("target") or data.get("phone") or data.get("email") or ""
        target = str(target).strip()

        if auth_type not in ["phone", "email"]:
            auth_type = "email" if "@" in target else "phone"

        if not target:
            return jsonify({"success": False, "error": "Mobile number or email address is required."}), 400

        # Request OTP from DB (handles rate limits, 5-minute expiry, salt, and hash storage)
        success, otp_code, is_existing, user_data, err_msg = db.request_otp(target, auth_type)
        if not success:
            return jsonify({"success": False, "error": err_msg}), 400

        # Deliver OTP via real provider
        recipient_name = user_data["name"] if user_data and user_data.get("name") else "Valued Customer"
        delivery_success = False
        delivery_msg = ""

        if auth_type == "phone":
            delivery_success, delivery_msg = send_sms_otp(target, otp_code)
        else:
            delivery_success, delivery_msg = send_email_otp(target, otp_code, recipient_name=recipient_name)

        if not delivery_success:
            return jsonify({
                "success": False,
                "error": delivery_msg,
                "provider_unconfigured": True
            }), 400

        return jsonify({
            "success": True,
            "auth_type": auth_type,
            "target_masked": mask_target(target, auth_type),
            "is_existing": is_existing,
            "user_name": user_data["name"] if user_data else "",
            "message": delivery_msg
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/auth/verify-otp", methods=["POST"])
def auth_verify_otp():
    """
    Verify entered OTP against securely hashed token.
    Enforces 5-minute expiry and max 5 attempts.
    """
    try:
        data = request.get_json(force=True) if request.is_json else request.form
        auth_type = data.get("type", "phone").lower().strip()
        target = data.get("target") or data.get("phone") or data.get("email") or ""
        target = str(target).strip()
        otp_code = str(data.get("otp_code") or "").strip()

        if auth_type not in ["phone", "email"]:
            auth_type = "email" if "@" in target else "phone"

        if not target or not otp_code:
            return jsonify({"success": False, "error": "Target and 6-digit OTP code are required."}), 400

        # Verify against stored hash in DB
        verified, error_msg, existing_user = db.verify_otp_token(target, auth_type, otp_code)
        if not verified:
            return jsonify({"success": False, "error": error_msg}), 400

        name = (data.get("name") or "").strip()
        address = (data.get("address") or "").strip()
        landmark = (data.get("landmark") or "").strip()
        city = (data.get("city") or "Jaipur").strip()
        state = (data.get("state") or "Rajasthan").strip()
        pincode = (data.get("pincode") or "").strip()

        # If it's a new user and name wasn't provided, prompt or set default
        user = db.get_or_create_user(
            target=target,
            target_type=auth_type,
            name=name,
            address=address,
            landmark=landmark,
            city=city,
            state=state,
            pincode=pincode
        )

        # Establish customer session
        session["user_id"] = user["id"]
        session["user_name"] = user["name"]
        session["user_phone"] = user.get("phone")
        session["user_email"] = user.get("email")

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
    session.pop("user_email", None)
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

# ----------------- ORDER PLACEMENT (MANDATORY CUSTOMER LOGIN) ----------------- #

@app.route("/api/order", methods=["POST"])
def place_order():
    try:
        user_id = session.get("user_id")
        if not user_id:
            return jsonify({
                "success": False,
                "requires_auth": True,
                "error": "Order place karne ke liye Login / OTP Verification anivarya hai."
            }), 401

        data = request.get_json(force=True)
        if not data or not data.get("items") or not data.get("name") or not data.get("phone"):
            return jsonify({"success": False, "error": "Missing required order details."}), 400

        saved_order = db.save_order(data, user_id=user_id)

        items_summary = "\n".join([
            f"• {item.get('name')} ({item.get('size')}g) × {item.get('qty')} = ₹{int(float(item.get('price', 0)) * int(item.get('qty', 1)))}"
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
        return jsonify({"success": False, "error": "Please provide an Order ID or Phone Number."}), 400

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
        return jsonify({"success": True, "message": "Inquiry submitted successfully! We will contact you shortly."})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# ----------------- ADMIN 2-STEP AUTHENTICATION (PASSWORD + OTP) ----------------- #

@app.route("/admin/login", methods=["GET"])
def admin_login_page():
    if session.get("admin_logged_in"):
        return redirect(url_for("admin_dashboard"))
    return render_template("admin_login.html")

@app.route("/api/admin/login-step1", methods=["POST"])
def api_admin_login_step1():
    """
    Step 1: Admin enters registered identifier (email/phone) and password.
    Server verifies credentials and dispatches a 6-digit OTP to the registered channel.
    """
    try:
        data = request.get_json(force=True) if request.is_json else request.form
        identifier = str(data.get("identifier") or "").strip()
        password = str(data.get("password") or "").strip()
        preferred_channel = str(data.get("channel") or "").lower().strip()

        if not identifier or not password:
            return jsonify({"success": False, "error": "Registered admin email/phone and password are required."}), 400

        # Verify admin credentials against admin_users table
        valid, admin_data = db.verify_admin_password(identifier, password)
        if not valid:
            return jsonify({"success": False, "error": "Invalid admin credentials. Access denied."}), 401

        # Determine target and channel
        if not preferred_channel:
            preferred_channel = "email" if "@" in identifier else "phone"

        target = admin_data["email"] if preferred_channel == "email" else admin_data["phone"]

        # Generate OTP
        success, otp_code, _, _, err_msg = db.request_otp(target, preferred_channel)
        if not success:
            return jsonify({"success": False, "error": err_msg}), 400

        # Deliver OTP to Admin
        delivery_success = False
        delivery_msg = ""
        if preferred_channel == "email":
            delivery_success, delivery_msg = send_email_otp(target, otp_code, recipient_name=admin_data["name"])
        else:
            delivery_success, delivery_msg = send_sms_otp(target, otp_code)

        if not delivery_success:
            return jsonify({
                "success": False,
                "error": delivery_msg,
                "provider_unconfigured": True
            }), 400

        # Temporarily store pending verification state in session
        session["admin_pending_id"] = admin_data["id"]
        session["admin_pending_target"] = target
        session["admin_pending_channel"] = preferred_channel
        session["admin_pending_name"] = admin_data["name"]

        return jsonify({
            "success": True,
            "message": f"Security OTP sent to registered admin {preferred_channel}: {mask_target(target, preferred_channel)}",
            "channel": preferred_channel,
            "target_masked": mask_target(target, preferred_channel)
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/admin/login-step2", methods=["POST"])
def api_admin_login_step2():
    """
    Step 2: Admin enters the 6-digit OTP received on their phone or email.
    Grants admin session only after successful cryptographic verification.
    """
    try:
        data = request.get_json(force=True) if request.is_json else request.form
        otp_code = str(data.get("otp_code") or "").strip()

        target = session.get("admin_pending_target")
        channel = session.get("admin_pending_channel")
        admin_id = session.get("admin_pending_id")

        if not target or not channel or not admin_id:
            return jsonify({"success": False, "error": "Session expired. Please restart admin login from step 1."}), 400

        verified, err_msg, _ = db.verify_otp_token(target, channel, otp_code)
        if not verified:
            return jsonify({"success": False, "error": err_msg}), 400

        admin_user = db.get_admin_user()

        # Grant authenticated admin session
        session["admin_logged_in"] = True
        session["admin_user"] = {
            "id": admin_user["id"],
            "name": admin_user["name"],
            "email": admin_user["email"],
            "phone": admin_user["phone"],
            "role": admin_user.get("role", "superadmin")
        }

        # Clean pending state
        session.pop("admin_pending_id", None)
        session.pop("admin_pending_target", None)
        session.pop("admin_pending_channel", None)
        session.pop("admin_pending_name", None)

        return jsonify({
            "success": True,
            "redirect": "/admin/dashboard",
            "message": f"Welcome, Admin {admin_user['name']}!"
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/admin/logout", methods=["GET", "POST"])
def admin_logout():
    session.pop("admin_logged_in", None)
    session.pop("admin_user", None)
    return redirect(url_for("admin_login_page"))

# ----------------- PROTECTED ADMIN DASHBOARD ----------------- #

@app.route("/admin")
@app.route("/admin/dashboard")
def admin_dashboard():
    if not session.get("admin_logged_in"):
        return redirect(url_for("admin_login_page"))
    admin_user = get_current_admin()
    return render_template("admin.html", admin_user=admin_user)

@app.route("/api/admin/profile")
def api_admin_profile():
    if not session.get("admin_logged_in"):
        return jsonify({"error": "Unauthorized"}), 401
    return jsonify({"success": True, "admin": get_current_admin()})

@app.route("/api/admin/stats")
def api_admin_stats():
    if not session.get("admin_logged_in"):
        return jsonify({"error": "Unauthorized"}), 401
    return jsonify(db.get_stats())

@app.route("/api/admin/orders")
def api_admin_orders():
    if not session.get("admin_logged_in"):
        return jsonify({"error": "Unauthorized"}), 401

    status_filter = request.args.get("status", "all")
    search = request.args.get("search", "")
    orders = db.get_orders(limit=200, status_filter=status_filter, search=search)
    return jsonify(orders)

@app.route("/api/admin/order/<order_id>/status", methods=["POST"])
def api_update_order_status(order_id):
    if not session.get("admin_logged_in"):
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json(force=True)
    new_status = data.get("order_status")
    payment_status = data.get("payment_status")

    if not new_status:
        return jsonify({"error": "Status is required"}), 400

    db.update_order_status(order_id, new_status, payment_status)
    return jsonify({"success": True, "order_id": order_id, "new_status": new_status})

@app.route("/api/admin/customer/<int:user_id>/orders")
def api_admin_customer_orders(user_id):
    if not session.get("admin_logged_in"):
        return jsonify({"error": "Unauthorized"}), 401
    orders = db.get_user_orders(user_id)
    customer = db.get_user_by_id(user_id)
    return jsonify({"success": True, "customer": customer, "orders": orders})

@app.route("/api/admin/products")
def api_admin_products():
    if not session.get("admin_logged_in"):
        return jsonify({"error": "Unauthorized"}), 401
    return jsonify(db.get_all_products(active_only=False))

@app.route("/api/admin/product/<product_id>/price", methods=["POST"])
def api_admin_update_product_price(product_id):
    if not session.get("admin_logged_in"):
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json(force=True)
    size = str(data.get("size", "")).strip()
    price = data.get("price")
    mrp = data.get("mrp")

    if not size or price is None:
        return jsonify({"error": "Size and price are required"}), 400

    success, msg = db.update_product_price(product_id, size, float(price), float(mrp) if mrp else None)
    return jsonify({"success": success, "message": msg})

@app.route("/api/admin/product/<product_id>/stock", methods=["POST"])
def api_admin_update_product_stock(product_id):
    if not session.get("admin_logged_in"):
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json(force=True)
    is_active = int(bool(data.get("is_active", True)))
    success, msg = db.update_product_stock(product_id, is_active)
    return jsonify({"success": success, "message": msg})

@app.route("/api/admin/inquiries")
def api_admin_inquiries():
    if not session.get("admin_logged_in"):
        return jsonify({"error": "Unauthorized"}), 401
    return jsonify(db.get_inquiries())

@app.route("/admin/invoice/<order_id>")
def admin_invoice(order_id):
    order = db.get_order_by_id(order_id)
    if not order:
        return "Order not found", 404

    is_admin = bool(session.get("admin_logged_in"))
    is_owner = bool(session.get("user_id") and order.get("user_id") == session.get("user_id"))

    if not is_admin and not is_owner:
        return redirect(url_for("admin_login_page"))

    return render_template("invoice.html", order=order, items=order.get("items", []))

@app.route("/api/admin/export-orders")
def export_orders():
    if not session.get("admin_logged_in"):
        return jsonify({"error": "Unauthorized"}), 401

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
