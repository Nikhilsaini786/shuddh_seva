from flask import Flask, render_template, request, jsonify, redirect, url_for, session, send_file
import json
from pathlib import Path
import os
import io
import csv
import base64
from datetime import datetime, timedelta
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # Graceful fallback: manually parse .env if present
    env_file = Path(__file__).resolve().parent / ".env"
    if env_file.exists():
        try:
            with open(env_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        k = k.strip()
                        v = v.strip().strip("'\"")
                        if k and k not in os.environ:
                            os.environ[k] = v
        except Exception:
            pass

import database as db
from services.otp_service import send_sms_otp, send_email_otp

app = Flask(__name__)
# Stable secret key for Vercel serverless persistence
app.secret_key = os.environ.get("SECRET_KEY", "shuddh_seva_production_master_secret_2026_x87z12")
app.config["SESSION_COOKIE_NAME"] = "shuddh_seva_session"
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=30)

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

@app.route("/login", methods=["GET", "POST"])
@app.route("/signup", methods=["GET", "POST"])
def auth_page():
    if request.method == "POST":
        action = request.form.get("action", "login")
        if action == "signup":
            name = request.form.get("name", "").strip()
            identifier = request.form.get("identifier", "").strip()
            password = request.form.get("password", "").strip()
            ok, msg, user = db.register_customer(name=name, identifier=identifier, password=password)
            if ok:
                session.permanent = True
                session["user_id"] = user["id"]
                session["user_name"] = user["name"]
                session["user_phone"] = user.get("phone")
                session["user_email"] = user.get("email")
                next_url = request.args.get("next") or url_for("home")
                return redirect(next_url)
            return render_template("auth.html", error=msg, active_tab="signup")
        else:
            identifier = request.form.get("identifier", "").strip()
            password = request.form.get("password", "").strip()
            ok, user_or_admin, is_admin, err_msg = db.authenticate_user_or_admin(identifier, password)
            if ok:
                session.permanent = True
                if is_admin:
                    session["admin_logged_in"] = True
                    session["admin_user"] = user_or_admin
                    return redirect(url_for("admin_dashboard"))
                else:
                    session["user_id"] = user_or_admin["id"]
                    session["user_name"] = user_or_admin["name"]
                    session["user_phone"] = user_or_admin.get("phone")
                    session["user_email"] = user_or_admin.get("email")
                    next_url = request.args.get("next") or url_for("home")
                    return redirect(next_url)
            return render_template("auth.html", error=err_msg, active_tab="login")

    if session.get("user_id"):
        return redirect(url_for("home"))
    if session.get("admin_logged_in"):
        return redirect(url_for("admin_dashboard"))
    return render_template("auth.html")

# ----------------- CUSTOMER SIGNUP & LOGIN (PASSWORD-BASED / NO OTP) ----------------- #

@app.route("/api/auth/signup", methods=["POST"])
@app.route("/api/auth/register", methods=["POST"])
def auth_signup():
    """Create a new customer account with name, mobile/email, and password."""
    try:
        data = request.get_json(force=True) if request.is_json else request.form
        name = (data.get("name") or "").strip()
        identifier = (data.get("identifier") or data.get("phone") or data.get("email") or "").strip()
        password = (data.get("password") or "").strip()
        phone = (data.get("phone") or "").strip()
        email = (data.get("email") or "").strip()
        address = (data.get("address") or "").strip()
        landmark = (data.get("landmark") or "").strip()
        city = (data.get("city") or "Jaipur").strip()
        state = (data.get("state") or "Rajasthan").strip()
        pincode = (data.get("pincode") or "").strip()

        ok, msg, user = db.register_customer(
            name=name,
            identifier=identifier,
            password=password,
            phone=phone,
            email=email,
            address=address,
            landmark=landmark,
            city=city,
            state=state,
            pincode=pincode
        )

        if not ok:
            return jsonify({"success": False, "error": msg}), 400

        # Login new customer automatically
        session.permanent = True
        session["user_id"] = user["id"]
        session["user_name"] = user["name"]
        session["user_phone"] = user.get("phone")
        session["user_email"] = user.get("email")

        return jsonify({
            "success": True,
            "message": msg,
            "user": user,
            "redirect": "/"
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/auth/login", methods=["POST"])
@app.route("/api/auth/signin", methods=["POST"])
def auth_login():
    """
    Unified Sign In for both Customers and Admin from the SAME login interface.
    Normal users never see admin options: if Admin logs in, it takes them straight
    to /admin/dashboard; if Customer logs in, it sets customer session!
    """
    try:
        data = request.get_json(force=True) if request.is_json else request.form
        identifier = (data.get("identifier") or data.get("phone") or data.get("email") or "").strip()
        password = (data.get("password") or "").strip()

        if not identifier or not password:
            return jsonify({"success": False, "error": "Please enter your mobile/email and password."}), 400

        ok, user_or_admin, is_admin, err_msg = db.authenticate_user_or_admin(identifier, password)
        if not ok:
            return jsonify({"success": False, "error": err_msg or "Invalid login credentials."}), 401

        session.permanent = True

        if is_admin:
            # Grant Admin Session
            session["admin_logged_in"] = True
            session["admin_user"] = {
                "id": user_or_admin["id"],
                "name": user_or_admin["name"],
                "email": user_or_admin["email"],
                "phone": user_or_admin["phone"],
                "role": user_or_admin.get("role", "superadmin")
            }
            return jsonify({
                "success": True,
                "is_admin": True,
                "message": f"Welcome, Admin {user_or_admin['name']}!",
                "redirect": "/admin/dashboard"
            })
        else:
            # Grant Customer Session
            session["user_id"] = user_or_admin["id"]
            session["user_name"] = user_or_admin["name"]
            session["user_phone"] = user_or_admin.get("phone")
            session["user_email"] = user_or_admin.get("email")
            return jsonify({
                "success": True,
                "is_admin": False,
                "message": f"Welcome back, {user_or_admin['name']}!",
                "user": user_or_admin,
                "redirect": "/"
            })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# ----------------- CUSTOMER OTP AUTHENTICATION (LEGACY FALLBACK) ----------------- #

@app.route("/api/auth/send-otp", methods=["POST"])
def auth_send_otp():
    """
    Generate and deliver 6-digit OTP via SMS / Email.
    On Vercel (or when Twilio/SMTP are unconfigured), delivers in instant test mode
    so signup/login is 100% working out of the box!
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

        # Check if target belongs to Admin
        is_admin_target = (db.normalize_phone(target) == "6350474290" or db.normalize_email(target) == "infosevaspice@gmail.com")

        # Request OTP from DB
        success, otp_code, is_existing, user_data, err_msg = db.request_otp(target, auth_type)
        if not success:
            return jsonify({"success": False, "error": err_msg}), 400

        # Attempt real provider delivery
        recipient_name = user_data["name"] if user_data and user_data.get("name") else "Valued Customer"
        delivery_success = False
        delivery_msg = ""

        if auth_type == "phone":
            delivery_success, delivery_msg = send_sms_otp(target, otp_code)
        else:
            delivery_success, delivery_msg = send_email_otp(target, otp_code, recipient_name=recipient_name)

        if not delivery_success:
            # When Twilio / SMTP are not yet configured on Vercel or local machine,
            # allow instant verification mode so signup and login work seamlessly!
            return jsonify({
                "success": True,
                "auth_type": auth_type,
                "target_masked": mask_target(target, auth_type),
                "is_existing": is_existing,
                "is_admin": is_admin_target,
                "user_name": user_data["name"] if user_data else "",
                "demo_mode": True,
                "demo_otp": otp_code,
                "message": f"Verification code: {otp_code} (Twilio/SMTP setup pending in .env)"
            })

        return jsonify({
            "success": True,
            "auth_type": auth_type,
            "target_masked": mask_target(target, auth_type),
            "is_existing": is_existing,
            "is_admin": is_admin_target,
            "user_name": user_data["name"] if user_data else "",
            "demo_mode": False,
            "message": delivery_msg
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/auth/verify-otp", methods=["POST"])
def auth_verify_otp():
    """Verify entered 6-digit OTP and establish customer session."""
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

        verified, error_msg, existing_user = db.verify_otp_token(target, auth_type, otp_code)
        if not verified:
            return jsonify({"success": False, "error": error_msg}), 400

        name = (data.get("name") or "").strip()
        address = (data.get("address") or "").strip()
        landmark = (data.get("landmark") or "").strip()
        city = (data.get("city") or "Jaipur").strip()
        state = (data.get("state") or "Rajasthan").strip()
        pincode = (data.get("pincode") or "").strip()

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

        session.permanent = True
        session["user_id"] = user["id"]
        session["user_name"] = user["name"]
        session["user_phone"] = user.get("phone")
        session["user_email"] = user.get("email")

        # If user is admin phone or email, also grant admin session
        if db.normalize_phone(target) == "6350474290" or db.normalize_email(target) == "infosevaspice@gmail.com":
            admin_user = db.get_admin_user()
            session["admin_logged_in"] = True
            session["admin_user"] = admin_user

        return jsonify({
            "success": True,
            "message": f"Welcome, {user['name']}!",
            "user": user,
            "is_admin": bool(session.get("admin_logged_in"))
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
        return jsonify({
            "logged_in": True,
            "user": user,
            "is_admin": bool(session.get("admin_logged_in"))
        })
    return jsonify({"logged_in": False, "is_admin": bool(session.get("admin_logged_in"))})

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

# ----------------- DIRECT STORE OWNER ADMIN LOGIN ----------------- #

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login_page():
    """
    Direct Admin Login:
    Admin logs in with their email/phone + password and directly opens the Admin Dashboard!
    """
    if request.method == "POST":
        data = request.get_json(silent=True) or request.form
        identifier = str(data.get("identifier") or data.get("email") or data.get("phone") or "").strip()
        password = str(data.get("password") or "").strip()

        if not identifier or not password:
            if request.is_json:
                return jsonify({"success": False, "error": "Registered Email/Phone and Password are required."}), 400
            return render_template("admin_login.html", error="Please enter your admin credentials.")

        valid, admin_data = db.verify_admin_password(identifier, password)
        if valid:
            session.permanent = True
            session["admin_logged_in"] = True
            session["admin_user"] = {
                "id": admin_data["id"],
                "name": admin_data["name"],
                "email": admin_data["email"],
                "phone": admin_data["phone"],
                "role": admin_data.get("role", "superadmin")
            }
            if request.is_json:
                return jsonify({
                    "success": True,
                    "redirect": url_for("admin_dashboard"),
                    "admin": session["admin_user"],
                    "message": f"Welcome, Admin {admin_data['name']}!"
                })
            return redirect(url_for("admin_dashboard"))
        else:
            if request.is_json:
                return jsonify({"success": False, "error": "Incorrect admin password or email/phone."}), 401
            return render_template("admin_login.html", error="Invalid admin password. Default is Shuddh@Admin2026! or shuddh123")

    if session.get("admin_logged_in"):
        return redirect(url_for("admin_dashboard"))
    return render_template("admin_login.html")

@app.route("/api/admin/login", methods=["POST"])
@app.route("/api/admin/direct-login", methods=["POST"])
def api_admin_direct_login():
    """Direct API endpoint for store owner login."""
    data = request.get_json(force=True) if request.is_json else request.form
    identifier = str(data.get("identifier") or "").strip()
    password = str(data.get("password") or "").strip()

    valid, admin_data = db.verify_admin_password(identifier, password)
    if valid:
        session.permanent = True
        session["admin_logged_in"] = True
        session["admin_user"] = {
            "id": admin_data["id"],
            "name": admin_data["name"],
            "email": admin_data["email"],
            "phone": admin_data["phone"],
            "role": admin_data.get("role", "superadmin")
        }
        return jsonify({
            "success": True,
            "redirect": "/admin/dashboard",
            "admin": session["admin_user"],
            "message": f"Welcome Admin {admin_data['name']}!"
        })
    return jsonify({"success": False, "error": "Invalid admin credentials."}), 401

@app.route("/api/admin/login-step1", methods=["POST"])
def api_admin_login_step1():
    """Fallback Step 1 for optional 2FA OTP verification."""
    try:
        data = request.get_json(force=True) if request.is_json else request.form
        identifier = str(data.get("identifier") or "").strip()
        password = str(data.get("password") or "").strip()
        preferred_channel = str(data.get("channel") or "").lower().strip()

        valid, admin_data = db.verify_admin_password(identifier, password)
        if not valid:
            return jsonify({"success": False, "error": "Invalid admin credentials."}), 401

        if not preferred_channel:
            preferred_channel = "email" if "@" in identifier else "phone"

        target = admin_data["email"] if preferred_channel == "email" else admin_data["phone"]

        success, otp_code, _, _, err_msg = db.request_otp(target, preferred_channel)
        if not success:
            return jsonify({"success": False, "error": err_msg}), 400

        delivery_success = False
        delivery_msg = ""
        if preferred_channel == "email":
            delivery_success, delivery_msg = send_email_otp(target, otp_code, recipient_name=admin_data["name"])
        else:
            delivery_success, delivery_msg = send_sms_otp(target, otp_code)

        session["admin_pending_id"] = admin_data["id"]
        session["admin_pending_target"] = target
        session["admin_pending_channel"] = preferred_channel
        session["admin_pending_name"] = admin_data["name"]

        if not delivery_success:
            return jsonify({
                "success": True,
                "message": f"Security OTP: {otp_code} (Setup mode)",
                "channel": preferred_channel,
                "target_masked": mask_target(target, preferred_channel),
                "demo_mode": True,
                "demo_otp": otp_code
            })

        return jsonify({
            "success": True,
            "message": f"Security OTP sent to {preferred_channel}: {mask_target(target, preferred_channel)}",
            "channel": preferred_channel,
            "target_masked": mask_target(target, preferred_channel)
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/admin/login-step2", methods=["POST"])
def api_admin_login_step2():
    """Verify admin OTP and open dashboard."""
    try:
        data = request.get_json(force=True) if request.is_json else request.form
        otp_code = str(data.get("otp_code") or "").strip()

        target = session.get("admin_pending_target")
        channel = session.get("admin_pending_channel")
        admin_id = session.get("admin_pending_id")

        if not target or not channel or not admin_id:
            return jsonify({"success": False, "error": "Session expired. Please enter your password again."}), 400

        verified, err_msg, _ = db.verify_otp_token(target, channel, otp_code)
        if not verified:
            return jsonify({"success": False, "error": err_msg}), 400

        admin_user = db.get_admin_user()
        session.permanent = True
        session["admin_logged_in"] = True
        session["admin_user"] = {
            "id": admin_user["id"],
            "name": admin_user["name"],
            "email": admin_user["email"],
            "phone": admin_user["phone"],
            "role": admin_user.get("role", "superadmin")
        }

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

# ----------------- ADMIN PRODUCT MANAGEMENT (IMAGE & PRICE) ----------------- #

@app.route("/api/admin/product/<product_id>/price", methods=["POST"])
def api_admin_update_product_price(product_id):
    """Update price and MRP for a pack size."""
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

@app.route("/api/admin/product/<product_id>/image", methods=["POST"])
def api_admin_update_product_image(product_id):
    """
    Update product front or back packaging image.
    Supports file uploads (saved as file or Data URL on Vercel) and image URLs.
    """
    if not session.get("admin_logged_in"):
        return jsonify({"error": "Unauthorized"}), 401

    side = request.form.get("side") or (request.json.get("side") if request.is_json else "front")
    side = "back" if str(side).lower() == "back" else "front"

    image_val = ""

    # Check if a file was uploaded
    if "image_file" in request.files:
        file = request.files["image_file"]
        if file and file.filename:
            file_bytes = file.read()
            mime = file.mimetype or "image/png"

            # Try saving to static/images if directory is writable
            save_dir = BASE_DIR / "static" / "images"
            saved_local = False
            if save_dir.exists():
                try:
                    ext = Path(file.filename).suffix.lower() or ".png"
                    filename = f"{product_id}-{side}-custom{ext}"
                    filepath = save_dir / filename
                    with open(filepath, "wb") as f:
                        f.write(file_bytes)
                    image_val = filename
                    saved_local = True
                except Exception:
                    saved_local = False

            # If read-only filesystem (Vercel), store as Base64 Data URL
            if not saved_local:
                b64_str = base64.b64encode(file_bytes).decode("utf-8")
                image_val = f"data:{mime};base64,{b64_str}"

    elif request.is_json and request.json.get("image_url"):
        image_val = request.json.get("image_url").strip()
    elif request.form.get("image_url"):
        image_val = request.form.get("image_url").strip()

    if not image_val:
        return jsonify({"success": False, "error": "No image file or URL provided."}), 400

    success, msg = db.update_product_image(product_id, side, image_val)
    return jsonify({"success": success, "image": image_val, "message": msg})

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
