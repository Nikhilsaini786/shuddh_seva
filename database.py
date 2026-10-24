import sqlite3
import json
import hashlib
from pathlib import Path
from datetime import datetime
import os

if os.environ.get("VERCEL") or os.environ.get("AWS_LAMBDA_FUNCTION_NAME"):
    DB_PATH = Path("/tmp") / "shuddh_seva.db"
else:
    DB_PATH = Path(__file__).resolve().parent / "shuddh_seva.db"

def get_db():
    first_time = not DB_PATH.exists()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    if first_time:
        init_db_with_conn(conn)
    return conn

def hash_password(password):
    return hashlib.sha256(password.encode("utf-8")).hexdigest()

def init_db_with_conn(conn):
    c = conn.cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        phone TEXT UNIQUE NOT NULL,
        email TEXT,
        password_hash TEXT DEFAULT '',
        address TEXT,
        landmark TEXT,
        city TEXT DEFAULT 'Jaipur',
        state TEXT DEFAULT 'Rajasthan',
        pincode TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    c.execute("""
    CREATE TABLE IF NOT EXISTS otp_verifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        phone TEXT NOT NULL,
        otp_code TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        used INTEGER DEFAULT 0
    )
    """)
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
        order_status TEXT DEFAULT 'New Order',
        notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )
    """)
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
    c.execute("""
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )
    """)
    defaults = [
        ("admin_password", "shuddh123"),
        ("admin_phone", "6350474290"),
        ("admin_email", "infosevaspice@gmail.com"),
        ("free_delivery_min", "499"),
        ("upi_id", "6350474290@paytm"),
        ("store_name", "Shuddh Seva Foods")
    ]
    for key, val in defaults:
        c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (key, val))
    conn.commit()

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    init_db_with_conn(conn)
    conn.close()

# ---------------- OTP AUTHENTICATION ---------------- #

def create_otp(phone):
    conn = get_db()
    c = conn.cursor()
    phone = phone.strip()
    import random
    otp_code = f"{random.randint(1000, 9999)}"
    
    # Mark prior unused OTPs for this phone as used
    c.execute("UPDATE otp_verifications SET used = 1 WHERE phone = ?", (phone,))
    c.execute("INSERT INTO otp_verifications (phone, otp_code) VALUES (?, ?)", (phone, otp_code))
    conn.commit()
    
    # Check if user already exists
    c.execute("SELECT id, name, phone, email, address, landmark, city, state, pincode FROM users WHERE phone = ?", (phone,))
    row = c.fetchone()
    is_existing = (row is not None)
    user_data = dict(row) if row else None
    conn.close()
    
    return otp_code, is_existing, user_data

def verify_otp_code(phone, otp_code):
    conn = get_db()
    c = conn.cursor()
    phone = phone.strip()
    otp_code = otp_code.strip()
    
    c.execute("""
    SELECT id FROM otp_verifications 
    WHERE phone = ? AND otp_code = ? AND used = 0 
    ORDER BY id DESC LIMIT 1
    """, (phone, otp_code))
    row = c.fetchone()
    
    if row:
        c.execute("UPDATE otp_verifications SET used = 1 WHERE id = ?", (row["id"],))
        conn.commit()
        
        c.execute("SELECT id, name, phone, email, address, landmark, city, state, pincode FROM users WHERE phone = ?", (phone,))
        u = c.fetchone()
        conn.close()
        return True, (dict(u) if u else None)
    
    conn.close()
    return False, None

def get_or_create_user_otp(phone, name="", address="", landmark="", city="Jaipur", state="Rajasthan", pincode=""):
    conn = get_db()
    c = conn.cursor()
    phone = phone.strip()
    
    c.execute("SELECT id, name, phone, email, address, landmark, city, state, pincode FROM users WHERE phone = ?", (phone,))
    row = c.fetchone()
    
    if row:
        user = dict(row)
        if name and name.strip() and user.get("name") != name.strip():
            c.execute("UPDATE users SET name = ? WHERE id = ?", (name.strip(), user["id"]))
            conn.commit()
            user["name"] = name.strip()
        conn.close()
        return user
    else:
        display_name = name.strip() if name.strip() else f"Customer {phone[-4:]}"
        c.execute("""
        INSERT INTO users (name, phone, password_hash, address, landmark, city, state, pincode)
        VALUES (?, ?, '', ?, ?, ?, ?, ?)
        """, (display_name, phone, address.strip(), landmark.strip(), city.strip() or "Jaipur", state.strip() or "Rajasthan", pincode.strip()))
        conn.commit()
        user_id = c.lastrowid
        
        c.execute("SELECT id, name, phone, email, address, landmark, city, state, pincode FROM users WHERE id = ?", (user_id,))
        user = dict(c.fetchone())
        conn.close()
        return user

def get_user_by_id(user_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id, name, phone, email, address, landmark, city, state, pincode, created_at FROM users WHERE id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None

def update_user_address(user_id, address, landmark, city, state, pincode):
    conn = get_db()
    c = conn.cursor()
    c.execute("""
    UPDATE users 
    SET address = ?, landmark = ?, city = ?, state = ?, pincode = ?
    WHERE id = ?
    """, (address, landmark, city, state, pincode, user_id))
    conn.commit()
    conn.close()

def get_user_orders(user_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM orders WHERE user_id = ? ORDER BY id DESC", (user_id,))
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    for r in rows:
        r["items"] = json.loads(r["items_json"])
    return rows

# ---------------- ORDERS & INQUIRIES ---------------- #

def save_order(data, user_id=None):
    conn = get_db()
    c = conn.cursor()
    
    timestamp = datetime.now().strftime("%y%m%d%H%M")
    import random
    order_id = f"SS-{timestamp}-{random.randint(100, 999)}"
    
    items_json = json.dumps(data.get("items", []), ensure_ascii=False)
    
    c.execute("""
    INSERT INTO orders (
        order_id, user_id, customer_name, phone, whatsapp, email,
        address, landmark, city, state, pincode,
        items_json, subtotal, discount, delivery_fee, total_amount,
        payment_method, payment_status, order_status, notes
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        order_id,
        user_id,
        data.get("name", "").strip(),
        data.get("phone", "").strip(),
        data.get("whatsapp", "").strip() or data.get("phone", "").strip(),
        data.get("email", "").strip(),
        data.get("address", "").strip(),
        data.get("landmark", "").strip(),
        data.get("city", "").strip(),
        data.get("state", "").strip(),
        data.get("pincode", "").strip(),
        items_json,
        float(data.get("subtotal", 0)),
        float(data.get("discount", 0)),
        float(data.get("delivery_fee", 0)),
        float(data.get("total", 0)),
        data.get("payment_method", "COD"),
        "Pending",
        "New Order",
        data.get("notes", "").strip()
    ))
    conn.commit()
    order_row_id = c.lastrowid
    
    # Also update user saved address for convenience
    if user_id:
        c.execute("""
        UPDATE users 
        SET address = ?, landmark = ?, city = ?, state = ?, pincode = ?
        WHERE id = ? AND (address IS NULL OR address = '')
        """, (
            data.get("address", "").strip(),
            data.get("landmark", "").strip(),
            data.get("city", "").strip(),
            data.get("state", "").strip(),
            data.get("pincode", "").strip(),
            user_id
        ))
        conn.commit()

    c.execute("SELECT * FROM orders WHERE id = ?", (order_row_id,))
    row = dict(c.fetchone())
    conn.close()
    row["items"] = json.loads(row["items_json"])
    return row

def get_orders(limit=100, status_filter=None, search=None):
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
        r["items"] = json.loads(r["items_json"])
    return rows

def get_order_by_id(order_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM orders WHERE order_id = ? OR phone = ? ORDER BY id DESC LIMIT 1", (order_id, order_id))
    row = c.fetchone()
    conn.close()
    if row:
        d = dict(row)
        d["items"] = json.loads(d["items_json"])
        return d
    return None

def update_order_status(order_id, new_status, payment_status=None):
    conn = get_db()
    c = conn.cursor()
    if payment_status:
        c.execute("UPDATE orders SET order_status = ?, payment_status = ? WHERE order_id = ?", (new_status, payment_status, order_id))
    else:
        c.execute("UPDATE orders SET order_status = ? WHERE order_id = ?", (new_status, order_id))
    conn.commit()
    conn.close()
    return True

def save_inquiry(data):
    conn = get_db()
    c = conn.cursor()
    c.execute("""
    INSERT INTO inquiries (name, phone, email, subject, message)
    VALUES (?, ?, ?, ?, ?)
    """, (
        data.get("name", "").strip(),
        data.get("phone", "").strip(),
        data.get("email", "").strip(),
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
    conn = get_db()
    c = conn.cursor()
    
    c.execute("SELECT COUNT(*) FROM orders")
    total_orders = c.fetchone()[0]
    
    c.execute("SELECT COALESCE(SUM(total_amount), 0) FROM orders WHERE order_status != 'Cancelled'")
    total_sales = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM orders WHERE order_status = 'New Order' OR order_status = 'Pending'")
    pending_orders = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM orders WHERE order_status = 'Delivered'")
    delivered_orders = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM inquiries WHERE status = 'Unread'")
    unread_inquiries = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM users")
    total_users = c.fetchone()[0]
    
    conn.close()
    return {
        "total_orders": total_orders,
        "total_sales": total_sales,
        "pending_orders": pending_orders,
        "delivered_orders": delivered_orders,
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
    print("Database updated and initialized successfully with OTP verification table.")
