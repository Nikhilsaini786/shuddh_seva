import sqlite3
import json
import hashlib
import hmac
import secrets
import os
from pathlib import Path
from datetime import datetime, timedelta

if os.environ.get("VERCEL") or os.environ.get("AWS_LAMBDA_FUNCTION_NAME"):
    DB_PATH = Path("/tmp") / "shuddh_seva.db"
    seed_db = Path(__file__).resolve().parent / "shuddh_seva.db"
    if not DB_PATH.exists() and seed_db.exists():
        import shutil
        try:
            shutil.copy2(seed_db, DB_PATH)
        except Exception:
            pass
else:
    DB_PATH = Path(__file__).resolve().parent / "shuddh_seva.db"

BASE_DIR = Path(__file__).resolve().parent

def get_db():
    first_time = not DB_PATH.exists()
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    try:
        conn.execute("PRAGMA journal_mode = WAL")
    except Exception:
        pass
    conn.row_factory = sqlite3.Row
    if first_time:
        init_db_with_conn(conn)
    return conn

def normalize_phone(phone: str) -> str:
    """Normalize phone to 10 digits."""
    if not phone:
        return ""
    digits = "".join(filter(str.isdigit, str(phone)))
    if len(digits) > 10 and digits.startswith("91"):
        digits = digits[-10:]
    return digits[-10:] if len(digits) >= 10 else digits

def normalize_email(email: str) -> str:
    """Normalize email address to lowercase and trimmed."""
    return email.strip().lower() if email else ""

def hash_with_salt(text: str, salt: str) -> str:
    """Compute secure SHA-256 hash with salt."""
    return hashlib.sha256((salt + text).encode("utf-8")).hexdigest()

def hash_otp(target: str, otp_code: str, salt: str) -> str:
    """Compute secure hash for OTP bound to the target recipient."""
    payload = f"{salt}:{target}:{otp_code}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()

def init_db_with_conn(conn):
    c = conn.cursor()

    # 1. Users Table
    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        phone TEXT UNIQUE,
        email TEXT UNIQUE,
        password_hash TEXT DEFAULT '',
        salt TEXT DEFAULT '',
        address TEXT,
        landmark TEXT,
        city TEXT DEFAULT 'Jaipur',
        state TEXT DEFAULT 'Rajasthan',
        pincode TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Check if users table needs 'salt' column
    c.execute("PRAGMA table_info(users)")
    user_cols = [r[1] for r in c.fetchall()]
    if "salt" not in user_cols:
        try:
            c.execute("ALTER TABLE users ADD COLUMN salt TEXT DEFAULT ''")
        except Exception:
            pass

    # 2. OTP Verifications Table (Check if old schema with 'phone' column exists, migrate if so)
    c.execute("PRAGMA table_info(otp_verifications)")
    otp_cols = [r[1] for r in c.fetchall()]
    if otp_cols and "target" not in otp_cols:
        c.execute("DROP TABLE otp_verifications")

    c.execute("""
    CREATE TABLE IF NOT EXISTS otp_verifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        target TEXT NOT NULL,
        target_type TEXT NOT NULL,
        otp_hash TEXT NOT NULL,
        salt TEXT NOT NULL,
        attempts INTEGER DEFAULT 0,
        max_attempts INTEGER DEFAULT 5,
        expires_at TIMESTAMP NOT NULL,
        used INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    c.execute("CREATE INDEX IF NOT EXISTS idx_otp_target ON otp_verifications (target, used)")

    # 3. Orders Table
    c.execute("""
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id TEXT UNIQUE NOT NULL,
        user_id INTEGER,
        customer_name TEXT NOT NULL,
        phone TEXT NOT NULL,
        whatsapp TEXT,
        email TEXT,
        address TEXT NOT NULL,
        landmark TEXT,
        city TEXT NOT NULL,
        state TEXT NOT NULL,
        pincode TEXT NOT NULL,
        items_json TEXT NOT NULL,
        subtotal REAL NOT NULL,
        discount REAL DEFAULT 0,
        delivery_fee REAL DEFAULT 0,
        total_amount REAL NOT NULL,
        payment_method TEXT NOT NULL,
        payment_status TEXT DEFAULT 'Pending',
        order_status TEXT DEFAULT 'Pending',
        notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )
    """)

    # 4. Order Items Table
    c.execute("""
    CREATE TABLE IF NOT EXISTS order_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id TEXT NOT NULL,
        product_id TEXT NOT NULL,
        product_name TEXT NOT NULL,
        size TEXT NOT NULL,
        quantity INTEGER NOT NULL,
        unit_price REAL NOT NULL,
        total_price REAL NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (order_id) REFERENCES orders (order_id)
    )
    """)

    # 5. Products Table
    c.execute("""
    CREATE TABLE IF NOT EXISTS products (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        hindi TEXT,
        tagline TEXT,
        category TEXT,
        badge TEXT,
        front TEXT,
        back TEXT,
        rating REAL DEFAULT 4.9,
        reviews_count INTEGER DEFAULT 100,
        description TEXT,
        short_desc TEXT,
        ingredients TEXT,
        fssai TEXT,
        storage TEXT,
        usage TEXT,
        manufacturer TEXT,
        customer_care TEXT,
        barcode TEXT,
        sizes_json TEXT NOT NULL,
        is_active INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # 6. Admin Users Table (For Ankit & Store Owners)
    c.execute("""
    CREATE TABLE IF NOT EXISTS admin_users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        phone TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        salt TEXT NOT NULL,
        role TEXT DEFAULT 'superadmin',
        is_active INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # 7. Customer Inquiries Table
    c.execute("""
    CREATE TABLE IF NOT EXISTS inquiries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        phone TEXT NOT NULL,
        email TEXT,
        subject TEXT,
        message TEXT NOT NULL,
        status TEXT DEFAULT 'Unread',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # 8. Settings Table
    c.execute("""
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )
    """)

    # Default settings
    defaults = [
        ("admin_name", "Ankit"),
        ("admin_phone", "6350474290"),
        ("admin_email", "infosevaspice@gmail.com"),
        ("free_delivery_min", "499"),
        ("upi_id", "6350474290@paytm"),
        ("store_name", "Shuddh Seva Foods")
    ]
    for key, val in defaults:
        c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (key, val))

    conn.commit()

    # Seed Admin User Ankit
    seed_admin_user(conn)

    # Seed Products from products.json if empty
    seed_products_if_empty(conn)


def seed_admin_user(conn):
    """Seed or update Ankit's admin account securely."""
    c = conn.cursor()
    admin_email = "infosevaspice@gmail.com"
    admin_phone = "6350474290"
    admin_name = "Ankit"
    admin_pass = os.environ.get("ADMIN_PASSWORD", "Shuddh@Admin2026!")

    c.execute("SELECT id FROM admin_users WHERE email = ? OR phone = ?", (admin_email, admin_phone))
    existing = c.fetchone()

    salt = secrets.token_hex(16)
    pass_hash = hash_with_salt(admin_pass, salt)

    if not existing:
        c.execute("""
        INSERT INTO admin_users (name, email, phone, password_hash, salt, role, is_active)
        VALUES (?, ?, ?, ?, ?, 'superadmin', 1)
        """, (admin_name, admin_email, admin_phone, pass_hash, salt))
        conn.commit()
    else:
        # If env ADMIN_PASSWORD is set explicitly, update hash
        if os.environ.get("ADMIN_PASSWORD"):
            c.execute("""
            UPDATE admin_users 
            SET password_hash = ?, salt = ?, name = ? 
            WHERE id = ?
            """, (pass_hash, salt, admin_name, existing[0]))
            conn.commit()


def seed_products_if_empty(conn):
    """Seed products table from products.json if empty or missing records."""
    c = conn.cursor()
    products_file = BASE_DIR / "products.json"
    if not products_file.exists():
        return

    with open(products_file, "r", encoding="utf-8") as f:
        products = json.load(f)

    for p in products:
        c.execute("SELECT id FROM products WHERE id = ?", (p["id"],))
        row = c.fetchone()
        sizes_json = json.dumps(p.get("sizes", {}), ensure_ascii=False)
        if not row:
            c.execute("""
            INSERT INTO products (
                id, name, hindi, tagline, category, badge, front, back,
                rating, reviews_count, description, short_desc, ingredients,
                fssai, storage, usage, manufacturer, customer_care, barcode, sizes_json, is_active
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
            """, (
                p["id"], p.get("name"), p.get("hindi"), p.get("tagline"),
                p.get("category"), p.get("badge"), p.get("front"), p.get("back"),
                p.get("rating", 4.9), p.get("reviews_count", 100),
                p.get("description"), p.get("short_desc"), p.get("ingredients"),
                p.get("fssai"), p.get("storage"), p.get("usage"),
                p.get("manufacturer"), p.get("customer_care"), p.get("barcode"),
                sizes_json
            ))
        else:
            # Keep product images and static info synced
            c.execute("""
            UPDATE products SET
                name = ?, hindi = ?, front = ?, back = ?
            WHERE id = ?
            """, (p.get("name"), p.get("hindi"), p.get("front"), p.get("back"), p["id"]))

    conn.commit()


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    init_db_with_conn(conn)
    conn.close()


# ---------------- SECURE OTP LIFECYCLE ---------------- #

def request_otp(target: str, target_type: str = "phone"):
    """
    Generate a real 6-digit OTP, store its secure hash with salt,
    enforce 5-minute expiry, rate limiting (45s cooldown, 5 reqs/hr),
    and invalidate previous unused OTPs for this target.
    Returns: (success: bool, otp_code_for_sender: str|None, is_existing: bool, user: dict|None, error_msg: str|None)
    """
    conn = get_db()
    c = conn.cursor()

    if target_type == "phone":
        normalized = normalize_phone(target)
        if len(normalized) != 10:
            conn.close()
            return False, None, False, None, "Please enter a valid 10-digit Indian mobile number."
    elif target_type == "email":
        normalized = normalize_email(target)
        if "@" not in normalized or "." not in normalized.split("@")[-1]:
            conn.close()
            return False, None, False, None, "Please enter a valid email address."
    else:
        conn.close()
        return False, None, False, None, "Invalid authentication type."

    now = datetime.now()

    # Rate limiting 1: 45 seconds cooldown between resends
    c.execute("""
    SELECT created_at FROM otp_verifications 
    WHERE target = ? ORDER BY id DESC LIMIT 1
    """, (normalized,))
    last_req = c.fetchone()
    if last_req:
        try:
            last_time = datetime.fromisoformat(str(last_req["created_at"]))
            if (now - last_time).total_seconds() < 45:
                wait_sec = int(45 - (now - last_time).total_seconds())
                conn.close()
                return False, None, False, None, f"Please wait {wait_sec} seconds before requesting a new OTP."
        except Exception:
            pass

    # Rate limiting 2: Max 5 requests per hour for the same target
    one_hour_ago = (now - timedelta(hours=1)).isoformat()
    c.execute("""
    SELECT COUNT(*) FROM otp_verifications 
    WHERE target = ? AND created_at > ?
    """, (normalized, one_hour_ago))
    count_last_hour = c.fetchone()[0]
    if count_last_hour >= 5:
        conn.close()
        return False, None, False, None, "Too many OTP requests. For security reasons, please try again in 1 hour."

    # Mark prior unused OTPs for this target as invalidated (used = 1)
    c.execute("UPDATE otp_verifications SET used = 1 WHERE target = ? AND used = 0", (normalized,))

    # Generate 6-digit numeric OTP
    from services.otp_service import generate_6digit_otp
    otp_code = generate_6digit_otp()

    salt = secrets.token_hex(16)
    otp_hash = hash_otp(normalized, otp_code, salt)
    expires_at = (now + timedelta(minutes=5)).isoformat()

    c.execute("""
    INSERT INTO otp_verifications (
        target, target_type, otp_hash, salt, attempts, max_attempts, expires_at, used, created_at
    ) VALUES (?, ?, ?, ?, 0, 5, ?, 0, ?)
    """, (normalized, target_type, otp_hash, salt, expires_at, now.isoformat()))
    conn.commit()

    # Check if user already exists
    if target_type == "phone":
        c.execute("SELECT * FROM users WHERE phone = ?", (normalized,))
    else:
        c.execute("SELECT * FROM users WHERE email = ?", (normalized,))
    row = c.fetchone()
    is_existing = (row is not None)
    user_data = dict(row) if row else None

    conn.close()
    return True, otp_code, is_existing, user_data, None


def verify_otp_token(target: str, target_type: str, entered_otp: str):
    """
    Verify entered 6-digit OTP against stored hash.
    Enforces 5-minute expiry, max 5 incorrect attempts, and secure timing comparison.
    Returns: (success: bool, error_msg: str|None, user: dict|None)
    """
    conn = get_db()
    c = conn.cursor()

    if target_type == "phone":
        normalized = normalize_phone(target)
    else:
        normalized = normalize_email(target)

    entered_otp = str(entered_otp).strip()

    c.execute("""
    SELECT id, otp_hash, salt, attempts, max_attempts, expires_at 
    FROM otp_verifications 
    WHERE target = ? AND used = 0 
    ORDER BY id DESC LIMIT 1
    """, (normalized,))
    record = c.fetchone()

    if not record:
        conn.close()
        return False, "No active OTP request found. Please request a new OTP.", None

    otp_id = record["id"]
    stored_hash = record["otp_hash"]
    salt = record["salt"]
    attempts = record["attempts"]
    max_attempts = record["max_attempts"]
    expires_at = datetime.fromisoformat(str(record["expires_at"]))

    # Check expiration (5 minutes)
    if datetime.now() > expires_at:
        c.execute("UPDATE otp_verifications SET used = 1 WHERE id = ?", (otp_id,))
        conn.commit()
        conn.close()
        return False, "This OTP has expired (5-minute validity). Please request a new OTP.", None

    # Check attempt limit
    if attempts >= max_attempts:
        c.execute("UPDATE otp_verifications SET used = 1 WHERE id = ?", (otp_id,))
        conn.commit()
        conn.close()
        return False, "Too many incorrect attempts. For security, this OTP is now invalid. Please request a new one.", None

    # Verify cryptographic hash
    computed_hash = hash_otp(normalized, entered_otp, salt)
    if hmac.compare_digest(computed_hash, stored_hash):
        # Successful verification: mark OTP as used
        c.execute("UPDATE otp_verifications SET used = 1 WHERE id = ?", (otp_id,))
        conn.commit()

        # Retrieve user if exists
        if target_type == "phone":
            c.execute("SELECT * FROM users WHERE phone = ?", (normalized,))
        else:
            c.execute("SELECT * FROM users WHERE email = ?", (normalized,))
        u = c.fetchone()
        user_dict = dict(u) if u else None
        conn.close()
        return True, None, user_dict
    else:
        # Increment attempt counter
        new_attempts = attempts + 1
        remaining = max_attempts - new_attempts
        if remaining <= 0:
            c.execute("UPDATE otp_verifications SET attempts = ?, used = 1 WHERE id = ?", (new_attempts, otp_id))
            conn.commit()
            conn.close()
            return False, "Incorrect OTP. Maximum 5 attempts exceeded. Please request a new OTP.", None
        else:
            c.execute("UPDATE otp_verifications SET attempts = ? WHERE id = ?", (new_attempts, otp_id))
            conn.commit()
            conn.close()
            return False, f"Incorrect OTP code. {remaining} attempt(s) remaining.", None


# ---------------- CUSTOMER PROFILE & ORDER HISTORY ---------------- #

def get_or_create_user(target: str, target_type: str, name: str = "", address: str = "",
                       landmark: str = "", city: str = "Jaipur", state: str = "Rajasthan", pincode: str = ""):
    """Create a new user or update an existing one after OTP verification."""
    conn = get_db()
    c = conn.cursor()

    if target_type == "phone":
        normalized = normalize_phone(target)
        c.execute("SELECT * FROM users WHERE phone = ?", (normalized,))
    else:
        normalized = normalize_email(target)
        c.execute("SELECT * FROM users WHERE email = ?", (normalized,))

    row = c.fetchone()

    if row:
        user = dict(row)
        updates = []
        params = []
        if name and name.strip() and user.get("name") != name.strip():
            updates.append("name = ?")
            params.append(name.strip())
            user["name"] = name.strip()
        if address and address.strip() and not user.get("address"):
            updates.append("address = ?")
            params.append(address.strip())
            user["address"] = address.strip()
        if pincode and pincode.strip() and not user.get("pincode"):
            updates.append("pincode = ?")
            params.append(pincode.strip())
            user["pincode"] = pincode.strip()

        if updates:
            params.append(user["id"])
            c.execute(f"UPDATE users SET {', '.join(updates)} WHERE id = ?", params)
            conn.commit()

        conn.close()
        return user
    else:
        display_name = name.strip() if name and name.strip() else ("Customer" if target_type == "email" else f"Customer {normalized[-4:]}")
        phone_val = normalized if target_type == "phone" else None
        email_val = normalized if target_type == "email" else None

        c.execute("""
        INSERT INTO users (name, phone, email, password_hash, salt, address, landmark, city, state, pincode)
        VALUES (?, ?, ?, '', '', ?, ?, ?, ?, ?)
        """, (display_name, phone_val, email_val, address.strip(), landmark.strip(), city.strip(), state.strip(), pincode.strip()))
        conn.commit()
        user_id = c.lastrowid

        c.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        user = dict(c.fetchone())
        conn.close()
        return user


def register_customer(name: str, identifier: str = "", password: str = "", phone: str = "", email: str = "",
                      address: str = "", landmark: str = "", city: str = "Jaipur", state: str = "Rajasthan", pincode: str = ""):
    """
    Create a new customer account with secure password hashing.
    identifier can be 10-digit Indian mobile number or email.
    """
    name = (name or "").strip()
    password = (password or "").strip()
    raw_ident = (identifier or phone or email or "").strip()

    if not name:
        return False, "Please enter your Full Name.", None
    if len(password) < 4:
        return False, "Password must be at least 4 characters.", None

    phone_val = normalize_phone(phone or raw_ident) if not ("@" in (phone or raw_ident)) else None
    email_val = normalize_email(email or raw_ident) if ("@" in (email or raw_ident)) else None

    if phone and not phone_val:
        phone_val = normalize_phone(phone)
    if email and not email_val:
        email_val = normalize_email(email)

    if not phone_val and not email_val:
        return False, "Please enter a valid 10-digit mobile number or email address.", None

    conn = get_db()
    c = conn.cursor()

    # Check for existing user
    if phone_val and email_val:
        c.execute("SELECT id FROM users WHERE phone = ? OR email = ?", (phone_val, email_val))
    elif phone_val:
        c.execute("SELECT id FROM users WHERE phone = ?", (phone_val,))
    else:
        c.execute("SELECT id FROM users WHERE email = ?", (email_val,))

    if c.fetchone():
        conn.close()
        return False, "An account with this mobile number or email already exists. Please Sign In.", None

    salt = secrets.token_hex(16)
    pass_hash = hash_with_salt(password, salt)

    c.execute("""
    INSERT INTO users (name, phone, email, password_hash, salt, address, landmark, city, state, pincode)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (name, phone_val, email_val, pass_hash, salt, address.strip(), landmark.strip(), city.strip(), state.strip(), pincode.strip()))
    conn.commit()
    user_id = c.lastrowid

    c.execute("SELECT id, name, phone, email, address, landmark, city, state, pincode, created_at FROM users WHERE id = ?", (user_id,))
    user = dict(c.fetchone())
    conn.close()
    return True, f"Welcome to Shuddh Seva Foods, {name}!", user


def authenticate_user_or_admin(identifier: str, password: str):
    """
    Authenticate against both admin_users and users table seamlessly from the same login.
    Returns: (success: bool, user_or_admin_data: dict|None, is_admin: bool, error_msg: str|None)
    """
    identifier = str(identifier or "").strip()
    password = str(password or "").strip()

    if not identifier or not password:
        return False, None, False, "Please enter your mobile/email and password."

    # 1. First check if credentials belong to Admin (Ankit)
    is_admin_valid, admin_data = verify_admin_password(identifier, password)
    if is_admin_valid:
        return True, admin_data, True, None

    # 2. Check regular customer users table
    conn = get_db()
    c = conn.cursor()
    norm_phone = normalize_phone(identifier)
    norm_email = normalize_email(identifier)

    if "@" in identifier:
        c.execute("SELECT * FROM users WHERE email = ? ORDER BY id DESC LIMIT 1", (norm_email,))
    else:
        c.execute("SELECT * FROM users WHERE phone = ? OR email = ? ORDER BY id DESC LIMIT 1", (norm_phone, norm_email))

    row = c.fetchone()
    if not row:
        conn.close()
        return False, None, False, "No account found with this mobile or email. Please click 'Create Account' to sign up."

    user = dict(row)
    stored_hash = user.get("password_hash") or ""
    salt = user.get("salt") or ""

    if stored_hash:
        computed = hash_with_salt(password, salt)
        if hmac.compare_digest(computed, stored_hash):
            conn.close()
            user.pop("password_hash", None)
            user.pop("salt", None)
            return True, user, False, None
        else:
            conn.close()
            return False, None, False, "Incorrect password. Please try again."
    else:
        # First time setting password for old record
        new_salt = secrets.token_hex(16)
        new_hash = hash_with_salt(password, new_salt)
        c.execute("UPDATE users SET password_hash = ?, salt = ? WHERE id = ?", (new_hash, new_salt, user["id"]))
        conn.commit()
        conn.close()
        user.pop("password_hash", None)
        user.pop("salt", None)
        return True, user, False, None


def get_user_by_id(user_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None


def get_user_orders(user_id):
    """Retrieve full customer order history with item breakdown."""
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM orders WHERE user_id = ? ORDER BY id DESC", (user_id,))
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    for r in rows:
        try:
            r["items"] = json.loads(r["items_json"])
        except Exception:
            r["items"] = []
    return rows


# ---------------- ORDERS & ORDER ITEMS ---------------- #

def save_order(data, user_id=None):
    """Save an order and insert individual line items into order_items."""
    conn = get_db()
    c = conn.cursor()

    timestamp = datetime.now().strftime("%y%m%d%H%M")
    order_id = f"SS-{timestamp}-{secrets.randbelow(900) + 100}"

    items = data.get("items", [])
    items_json = json.dumps(items, ensure_ascii=False)

    subtotal = float(data.get("subtotal", 0))
    discount = float(data.get("discount", 0))
    delivery_fee = float(data.get("delivery_fee", 0))
    total_amount = float(data.get("total", 0))

    c.execute("""
    INSERT INTO orders (
        order_id, user_id, customer_name, phone, whatsapp, email,
        address, landmark, city, state, pincode,
        items_json, subtotal, discount, delivery_fee, total_amount,
        payment_method, payment_status, order_status, notes
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Pending', ?)
    """, (
        order_id,
        user_id,
        data.get("name", "").strip(),
        normalize_phone(data.get("phone", "")),
        normalize_phone(data.get("whatsapp", "")) or normalize_phone(data.get("phone", "")),
        normalize_email(data.get("email", "")),
        data.get("address", "").strip(),
        data.get("landmark", "").strip(),
        data.get("city", "").strip(),
        data.get("state", "").strip(),
        data.get("pincode", "").strip(),
        items_json,
        subtotal,
        discount,
        delivery_fee,
        total_amount,
        data.get("payment_method", "COD"),
        "Pending",
        data.get("notes", "").strip()
    ))

    # Insert line items into order_items
    for it in items:
        p_id = str(it.get("id") or it.get("product_id") or "")
        p_name = str(it.get("name") or "")
        size = str(it.get("size") or "100")
        qty = int(it.get("qty", 1))
        unit_price = float(it.get("price", 0))
        tot_price = unit_price * qty

        c.execute("""
        INSERT INTO order_items (
            order_id, product_id, product_name, size, quantity, unit_price, total_price
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (order_id, p_id, p_name, size, qty, unit_price, tot_price))

    # Update user's saved address if missing
    if user_id:
        c.execute("""
        UPDATE users 
        SET address = COALESCE(NULLIF(address, ''), ?),
            landmark = COALESCE(NULLIF(landmark, ''), ?),
            city = COALESCE(NULLIF(city, ''), ?),
            state = COALESCE(NULLIF(state, ''), ?),
            pincode = COALESCE(NULLIF(pincode, ''), ?)
        WHERE id = ?
        """, (
            data.get("address", "").strip(),
            data.get("landmark", "").strip(),
            data.get("city", "").strip(),
            data.get("state", "").strip(),
            data.get("pincode", "").strip(),
            user_id
        ))

    conn.commit()

    c.execute("SELECT * FROM orders WHERE order_id = ?", (order_id,))
    row = dict(c.fetchone())
    conn.close()

    try:
        row["items"] = json.loads(row["items_json"])
    except Exception:
        row["items"] = items

    return row


def get_orders(limit=100, status_filter=None, search=None):
    """Retrieve orders with search and status filtering."""
    conn = get_db()
    c = conn.cursor()
    query = "SELECT * FROM orders WHERE 1=1"
    params = []

    if status_filter and status_filter != "all":
        query += " AND order_status = ?"
        params.append(status_filter)

    if search:
        query += " AND (order_id LIKE ? OR customer_name LIKE ? OR phone LIKE ? OR city LIKE ?)"
        s = f"%{search}%"
        params.extend([s, s, s, s])

    query += " ORDER BY id DESC LIMIT ?"
    params.append(limit)

    c.execute(query, params)
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    for r in rows:
        try:
            r["items"] = json.loads(r["items_json"])
        except Exception:
            r["items"] = []
    return rows


def get_order_by_id(order_id: str):
    """Lookup order by Order ID or phone."""
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM orders WHERE order_id = ? OR phone = ? ORDER BY id DESC LIMIT 1", (order_id, order_id))
    row = c.fetchone()
    conn.close()
    if row:
        d = dict(row)
        try:
            d["items"] = json.loads(d["items_json"])
        except Exception:
            d["items"] = []
        return d
    return None


def update_order_status(order_id: str, new_status: str, payment_status: str = None):
    """
    Update order status (Pending, Confirmed, Shipped, Delivered, Cancelled)
    and optional payment status.
    """
    valid_statuses = ["Pending", "Confirmed", "Shipped", "Delivered", "Cancelled", "New Order"]
    if new_status not in valid_statuses:
        new_status = "Pending"

    conn = get_db()
    c = conn.cursor()
    if payment_status:
        c.execute("UPDATE orders SET order_status = ?, payment_status = ? WHERE order_id = ?", (new_status, payment_status, order_id))
    else:
        c.execute("UPDATE orders SET order_status = ? WHERE order_id = ?", (new_status, order_id))
    conn.commit()
    conn.close()
    return True


# ---------------- ADMIN AUTHENTICATION & MANAGEMENT ---------------- #

def verify_admin_password(identifier: str, password: str):
    """
    Verify admin password against admin_users table.
    Identifier can be email ('infosevaspice@gmail.com'), phone ('6350474290'),
    or username ('ankit', 'admin').
    Returns: (success: bool, admin_data: dict|None)
    """
    conn = get_db()
    c = conn.cursor()
    norm_phone = normalize_phone(identifier)
    norm_email = normalize_email(identifier)
    raw_id = str(identifier).strip().lower()

    # Search admin by phone, email, name, or admin keywords
    c.execute("""
    SELECT * FROM admin_users 
    WHERE (email = ? OR phone = ? OR lower(name) = ? OR ? IN ('admin', 'ankit', 'storeadmin', 'owner')) AND is_active = 1
    """, (norm_email, norm_phone, raw_id, raw_id))
    admin_row = c.fetchone()

    # Fallback to first active admin if identifier was 'admin' or 'ankit'
    if not admin_row and raw_id in ["admin", "ankit", "owner", "6350474290", "infosevaspice@gmail.com"]:
        c.execute("SELECT * FROM admin_users WHERE is_active = 1 ORDER BY id ASC LIMIT 1")
        admin_row = c.fetchone()

    conn.close()

    if not admin_row:
        return False, None

    salt = admin_row["salt"]
    stored_hash = admin_row["password_hash"]
    computed_hash = hash_with_salt(password, salt)

    if hmac.compare_digest(computed_hash, stored_hash):
        return True, dict(admin_row)

    # Master fallback passwords for Ankit
    allowed_passwords = ["Shuddh@Admin2026!", "shuddh123"]
    env_pass = os.environ.get("ADMIN_PASSWORD")
    if env_pass:
        allowed_passwords.append(env_pass)

    if password in allowed_passwords:
        return True, dict(admin_row)

    return False, None


def get_admin_user():
    """Retrieve primary admin details."""
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id, name, email, phone, role FROM admin_users WHERE is_active = 1 ORDER BY id ASC LIMIT 1")
    row = c.fetchone()
    conn.close()
    return dict(row) if row else {
        "id": 1,
        "name": "Ankit",
        "email": "infosevaspice@gmail.com",
        "phone": "6350474290",
        "role": "superadmin"
    }


# ---------------- PRODUCT CATALOG MANAGEMENT (ADMIN CRUD) ---------------- #

def get_all_products(active_only=False):
    """Retrieve all products from the database, populated with sizes."""
    conn = get_db()
    c = conn.cursor()
    if active_only:
        c.execute("SELECT * FROM products WHERE is_active = 1 ORDER BY id ASC")
    else:
        c.execute("SELECT * FROM products ORDER BY id ASC")
    rows = [dict(r) for r in c.fetchall()]
    conn.close()

    # Fallback to products.json if empty
    if not rows:
        products_file = BASE_DIR / "products.json"
        if products_file.exists():
            with open(products_file, "r", encoding="utf-8") as f:
                return json.load(f)

    for r in rows:
        try:
            r["sizes"] = json.loads(r["sizes_json"])
        except Exception:
            r["sizes"] = {}
    return rows


def update_product_price(product_id: str, size: str, price: float, mrp: float = None):
    """Update price and MRP for a specific product size."""
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT sizes_json FROM products WHERE id = ?", (product_id,))
    row = c.fetchone()
    if not row:
        conn.close()
        return False, "Product not found"

    try:
        sizes = json.loads(row["sizes_json"])
    except Exception:
        sizes = {}

    if size not in sizes:
        sizes[size] = {}

    sizes[size]["price"] = float(price)
    if mrp is not None:
        sizes[size]["mrp"] = float(mrp)
        savings = float(mrp) - float(price)
        sizes[size]["save"] = f"₹{int(savings)} OFF"

    c.execute("UPDATE products SET sizes_json = ? WHERE id = ?", (json.dumps(sizes, ensure_ascii=False), product_id))
    conn.commit()
    conn.close()
    return True, "Price updated successfully"


def update_product_stock(product_id: str, is_active: int):
    """Toggle product active/stock status."""
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE products SET is_active = ? WHERE id = ?", (1 if is_active else 0, product_id))
    conn.commit()
    conn.close()
    return True, "Product status updated"


def update_product_image(product_id: str, side: str, image_val: str):
    """Update front or back image for a product."""
    conn = get_db()
    c = conn.cursor()
    col = "front" if side == "front" else "back"
    c.execute(f"UPDATE products SET {col} = ? WHERE id = ?", (image_val, product_id))
    conn.commit()
    conn.close()
    return True, f"Product {side} image updated successfully"


def update_product_all_prices(product_id: str, sizes_dict: dict):
    """Update all sizes, prices and MRPs for a product."""
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE products SET sizes_json = ? WHERE id = ?", (json.dumps(sizes_dict, ensure_ascii=False), product_id))
    conn.commit()
    conn.close()
    return True, "All prices updated successfully"


# ---------------- INQUIRIES & METRICS ---------------- #

def save_inquiry(data):
    conn = get_db()
    c = conn.cursor()
    c.execute("""
    INSERT INTO inquiries (name, phone, email, subject, message)
    VALUES (?, ?, ?, ?, ?)
    """, (
        data.get("name", "").strip(),
        normalize_phone(data.get("phone", "")),
        normalize_email(data.get("email", "")),
        data.get("subject", "").strip(),
        data.get("message", "").strip()
    ))
    conn.commit()
    conn.close()
    return True


def get_inquiries(limit=50):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM inquiries ORDER BY id DESC LIMIT ?", (limit,))
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


def get_stats():
    """Calculate dashboard statistics."""
    conn = get_db()
    c = conn.cursor()

    c.execute("SELECT COUNT(*) FROM orders")
    total_orders = c.fetchone()[0]

    c.execute("SELECT COALESCE(SUM(total_amount), 0) FROM orders WHERE order_status != 'Cancelled'")
    total_sales = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM orders WHERE order_status = 'Pending' OR order_status = 'New Order'")
    pending_orders = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM orders WHERE order_status = 'Confirmed'")
    confirmed_orders = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM orders WHERE order_status = 'Shipped'")
    shipped_orders = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM orders WHERE order_status = 'Delivered'")
    delivered_orders = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM orders WHERE order_status = 'Cancelled'")
    cancelled_orders = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM inquiries WHERE status = 'Unread'")
    unread_inquiries = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM users")
    total_users = c.fetchone()[0]

    conn.close()
    return {
        "total_orders": total_orders,
        "total_sales": total_sales,
        "pending_orders": pending_orders,
        "confirmed_orders": confirmed_orders,
        "shipped_orders": shipped_orders,
        "delivered_orders": delivered_orders,
        "cancelled_orders": cancelled_orders,
        "unread_inquiries": unread_inquiries,
        "total_users": total_users
    }


def get_setting(key, default=None):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT value FROM settings WHERE key = ?", (key,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else default


def update_setting(key, value):
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
    conn.commit()
    conn.close()


if __name__ == "__main__":
    init_db()
    print("Database schema, tables, admin user and products initialized successfully.")
