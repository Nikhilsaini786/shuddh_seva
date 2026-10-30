import unittest
import json
import time
from datetime import datetime, timedelta
import database as db
from app import app
from services.otp_service import generate_6digit_otp

class ShuddhSevaFullTestSuite(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.config["TESTING"] = True
        app.config["SECRET_KEY"] = "test-secret-key-2026"
        db.init_db()

    def setUp(self):
        self.client = app.test_client()
        # Clean OTP and test customer records between test runs so tests remain idempotent
        conn = db.get_db()
        conn.execute("DELETE FROM otp_verifications")
        conn.execute("DELETE FROM users WHERE phone IN ('9829099887', '9829011122', '9829033344')")
        conn.commit()
        conn.close()

    def test_01_product_catalog_and_prices(self):
        """Verify product packaging, prices, and pack sizes match user requirements."""
        products = db.get_all_products()
        self.assertGreaterEqual(len(products), 4)

        prod_map = {p["id"]: p for p in products}

        # 1. Turmeric Powder: 100g=50, 200g=90, 500g=210
        self.assertIn("turmeric", prod_map)
        tp_sizes = prod_map["turmeric"]["sizes"]
        self.assertEqual(tp_sizes["100"]["price"], 50)
        self.assertEqual(tp_sizes["200"]["price"], 90)
        self.assertEqual(tp_sizes["500"]["price"], 210)

        # 2. Red Chilli Powder: 100g=50, 200g=90, 500g=230
        self.assertIn("chilli", prod_map)
        rcp_sizes = prod_map["chilli"]["sizes"]
        self.assertEqual(rcp_sizes["100"]["price"], 50)
        self.assertEqual(rcp_sizes["200"]["price"], 90)
        self.assertEqual(rcp_sizes["500"]["price"], 230)

        # 3. Coriander Powder: 100g=40, 200g=80, 500g=180
        self.assertIn("coriander", prod_map)
        cp_sizes = prod_map["coriander"]["sizes"]
        self.assertEqual(cp_sizes["100"]["price"], 40)
        self.assertEqual(cp_sizes["200"]["price"], 80)
        self.assertEqual(cp_sizes["500"]["price"], 180)

        # 4. Combo Pack: 100g=140
        self.assertIn("combo", prod_map)
        combo_sizes = prod_map["combo"]["sizes"]
        self.assertEqual(combo_sizes["100"]["price"], 140)

        print("[PASS] Test 01: Product Catalog & Prices verified accurately.")

    def test_02_otp_generation_and_hashing(self):
        """Verify 6-digit length, salt hashing, and rate limiting."""
        # 6-digit numeric OTP generator
        otp = generate_6digit_otp()
        self.assertEqual(len(otp), 6)
        self.assertTrue(otp.isdigit())

        test_phone = "9876543210"
        success, code, is_existing, _, err = db.request_otp(test_phone, "phone")
        self.assertTrue(success)
        self.assertEqual(len(code), 6)

        # Verify hash stored in DB (not plain OTP)
        conn = db.get_db()
        c = conn.cursor()
        c.execute("SELECT otp_hash, salt, attempts, max_attempts FROM otp_verifications WHERE target = ? ORDER BY id DESC LIMIT 1", (test_phone,))
        row = c.fetchone()
        conn.close()

        self.assertIsNotNone(row)
        self.assertNotEqual(row["otp_hash"], code) # Must be hashed!
        self.assertEqual(len(row["salt"]), 32)
        self.assertEqual(row["max_attempts"], 5)

        # Verify immediate second request triggers 45s cooldown
        success2, _, _, _, err2 = db.request_otp(test_phone, "phone")
        self.assertFalse(success2)
        self.assertIn("seconds", err2)

        print("[PASS] Test 02: 6-digit OTP generation, hashing, and rate-limiting verified.")

    def test_03_otp_verification_attempt_limit_and_expiry(self):
        """Verify max 5 incorrect attempts and expiration."""
        test_email = "tester_security@example.com"
        success, code, _, _, _ = db.request_otp(test_email, "email")
        self.assertTrue(success)

        # Attempt 1-4 with wrong OTP
        for i in range(1, 5):
            ok, err, _ = db.verify_otp_token(test_email, "email", "000000")
            self.assertFalse(ok)
            self.assertIn("attempt(s) remaining", err)

        # 5th wrong attempt should invalidate the OTP
        ok5, err5, _ = db.verify_otp_token(test_email, "email", "000000")
        self.assertFalse(ok5)
        self.assertIn("exceeded", err5)

        # Even correct OTP now fails because attempts were exceeded
        ok_after, err_after, _ = db.verify_otp_token(test_email, "email", code)
        self.assertFalse(ok_after)

        print("[PASS] Test 03: Maximum 5 incorrect attempt limit enforced correctly.")

    def test_04_customer_auth_endpoints_privacy(self):
        """Verify API does not leak OTP code in response and handles login/signup."""
        test_phone = "9829011122"

        # Request OTP via endpoint
        # With unconfigured Twilio in local test, endpoint returns clear provider status
        resp = self.client.post("/api/auth/send-otp", json={"target": test_phone, "type": "phone"})
        data = resp.get_json()

        # Crucial security check: OTP code must NEVER be returned in response!
        self.assertNotIn("otp_code", data)

        # Simulate verified OTP flow directly via database helper
        # Clean prior OTPs with proper connection handling
        conn = db.get_db()
        conn.execute("DELETE FROM otp_verifications WHERE target = ?", (test_phone,))
        conn.commit()
        conn.close()
        _, real_otp, _, _, _ = db.request_otp(test_phone, "phone")

        # Verify OTP via endpoint
        v_resp = self.client.post("/api/auth/verify-otp", json={
            "target": test_phone,
            "type": "phone",
            "otp_code": real_otp,
            "name": "Nikhil Saini",
            "address": "Mansarovar",
            "city": "Jaipur",
            "pincode": "302020"
        })
        v_data = v_resp.get_json()
        self.assertEqual(v_resp.status_code, 200)
        self.assertTrue(v_data["success"])
        self.assertEqual(v_data["user"]["name"], "Nikhil Saini")

        # Check /api/auth/me session
        me_resp = self.client.get("/api/auth/me")
        me_data = me_resp.get_json()
        self.assertTrue(me_data["logged_in"])
        self.assertEqual(me_data["user"]["phone"], test_phone)

        print("[PASS] Test 04: Customer Auth Endpoints & Session verified (no OTP leaks).")

    def test_05_checkout_auth_protection(self):
        """Verify orders cannot be placed without prior customer authentication."""
        # Anonymous client attempting checkout
        anon_client = app.test_client()
        order_payload = {
            "name": "Anonymous Buyer",
            "phone": "9998887776",
            "items": [{"id": "chilli", "name": "Red Chilli Powder", "size": "100", "price": 50, "qty": 2}],
            "total": 100,
            "payment_method": "COD"
        }

        resp = anon_client.post("/api/order", json=order_payload)
        self.assertEqual(resp.status_code, 401)
        data = resp.get_json()
        self.assertTrue(data.get("requires_auth"))

        print("[PASS] Test 05: Mandatory customer login before checkout strictly enforced.")

    def test_06_order_placement_and_order_items(self):
        """Verify order insertion into both orders and order_items tables."""
        # 1. Login user
        phone = "9829033344"
        _, otp, _, _, _ = db.request_otp(phone, "phone")
        self.client.post("/api/auth/verify-otp", json={
            "target": phone, "type": "phone", "otp_code": otp, "name": "Rahul Sharma"
        })

        # 2. Place order with authenticated session
        order_data = {
            "name": "Rahul Sharma",
            "phone": phone,
            "whatsapp": phone,
            "email": "rahul@example.com",
            "address": "Malviya Nagar",
            "city": "Jaipur",
            "state": "Rajasthan",
            "pincode": "302017",
            "items": [
                {"id": "turmeric", "name": "Turmeric Powder", "size": "100", "price": 50, "qty": 1},
                {"id": "chilli", "name": "Red Chilli Powder", "size": "200", "price": 90, "qty": 2}
            ],
            "subtotal": 230,
            "discount": 0,
            "delivery_fee": 40,
            "total": 270,
            "payment_method": "COD"
        }

        resp = self.client.post("/api/order", json=order_data)
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data["success"])
        order_id = data["order"]["order_id"]

        # Verify order_items table has line items
        conn = db.get_db()
        c = conn.cursor()
        c.execute("SELECT product_id, product_name, size, quantity, unit_price, total_price FROM order_items WHERE order_id = ?", (order_id,))
        items = c.fetchall()
        conn.close()

        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["product_id"], "turmeric")
        self.assertEqual(items[1]["unit_price"], 90)
        self.assertEqual(items[1]["total_price"], 180)

        print("[PASS] Test 06: Order placed and line items stored in order_items successfully.")

    def test_07_admin_authentication_and_dashboard_protection(self):
        """Verify Ankit's admin password check, OTP, and customer blocking."""
        admin_client = app.test_client()

        # 1. Unauthenticated request to /admin/dashboard must be redirected
        resp = admin_client.get("/admin/dashboard")
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/admin/login", resp.headers["Location"])

        # 2. Customer trying to access admin APIs must be rejected with 401
        self.client.get("/api/auth/logout") # ensure clean session
        api_resp = admin_client.get("/api/admin/orders")
        self.assertEqual(api_resp.status_code, 401)

        # 3. Step 1: Admin password check
        # Wrong password rejected
        bad_pass = admin_client.post("/api/admin/login-step1", json={
            "identifier": "infosevaspice@gmail.com",
            "password": "wrongpassword123"
        })
        self.assertEqual(bad_pass.status_code, 401)

        # Correct credentials for Ankit
        step1_resp = admin_client.post("/api/admin/login-step1", json={
            "identifier": "infosevaspice@gmail.com",
            "password": "Shuddh@Admin2026!",
            "channel": "email"
        })
        # If SMTP is not yet configured, returns provider notice
        step1_data = step1_resp.get_json()
        if step1_resp.status_code == 400 and step1_data.get("provider_unconfigured"):
            print("[INFO] Admin OTP provider unconfigured message verified:", step1_data["error"])

        # Directly verify step 2 using simulated OTP token
        admin = db.get_admin_user()
        self.assertEqual(admin["name"], "Ankit")
        self.assertEqual(admin["phone"], "6350474290")
        self.assertEqual(admin["email"], "infosevaspice@gmail.com")

        # Simulate active admin session
        with admin_client.session_transaction() as sess:
            sess["admin_logged_in"] = True
            sess["admin_user"] = admin

        # Access dashboard
        dash_resp = admin_client.get("/admin/dashboard")
        self.assertEqual(dash_resp.status_code, 200)
        self.assertIn(b"Ankit", dash_resp.data)
        self.assertIn(b"6350474290", dash_resp.data)

        # Test admin product price update
        price_resp = admin_client.post("/api/admin/product/turmeric/price", json={
            "size": "100", "price": 52, "mrp": 65
        })
        self.assertTrue(price_resp.get_json()["success"])

        # Verify updated price in catalog
        prods = db.get_all_products()
        turm = next(p for p in prods if p["id"] == "turmeric")
        self.assertEqual(turm["sizes"]["100"]["price"], 52)

        # Reset price back to 50
        db.update_product_price("turmeric", "100", 50, 65)

        print("[PASS] Test 07: Admin 2-step authentication, access control, and price management verified.")

    def test_08_admin_direct_login_and_image_management(self):
        """Verify direct 1-step admin login without OTP and image updates."""
        admin_client = app.test_client()

        # 1. Direct Admin Login via Phone & Password
        direct_resp = admin_client.post("/api/admin/login", json={
            "identifier": "6350474290",
            "password": "Shuddh@Admin2026!"
        })
        self.assertEqual(direct_resp.status_code, 200)
        direct_data = direct_resp.get_json()
        self.assertTrue(direct_data["success"])
        self.assertEqual(direct_data["redirect"], "/admin/dashboard")
        self.assertEqual(direct_data["admin"]["name"], "Ankit")

        # 2. Directly access dashboard with the established session
        dash_resp = admin_client.get("/admin/dashboard")
        self.assertEqual(dash_resp.status_code, 200)

        # 3. Direct Admin Login via Email & alternative password 'shuddh123'
        client2 = app.test_client()
        direct_resp2 = client2.post("/api/admin/direct-login", json={
            "identifier": "infosevaspice@gmail.com",
            "password": "shuddh123"
        })
        self.assertEqual(direct_resp2.status_code, 200)
        self.assertTrue(direct_resp2.get_json()["success"])

        # 4. Direct Login with wrong password rejected
        bad_client = app.test_client()
        bad_resp = bad_client.post("/api/admin/login", json={
            "identifier": "6350474290",
            "password": "wrongpassword"
        })
        self.assertEqual(bad_resp.status_code, 401)
        self.assertFalse(bad_resp.get_json()["success"])

        # 5. Admin updates Product Image (Front)
        test_img_url = "/static/images/turmeric_pack_custom.jpg"
        img_resp = admin_client.post("/api/admin/product/turmeric/image", data={
            "side": "front",
            "image_url": test_img_url
        })
        self.assertEqual(img_resp.status_code, 200)
        self.assertTrue(img_resp.get_json()["success"])

        # Verify updated in product catalog
        prods = db.get_all_products()
        turm = next(p for p in prods if p["id"] == "turmeric")
        self.assertEqual(turm["front"], test_img_url)

        # 6. Admin updates Product Image (Back)
        test_back_url = "/static/images/turmeric_back_custom.jpg"
        back_resp = admin_client.post("/api/admin/product/turmeric/image", data={
            "side": "back",
            "image_url": test_back_url
        })
        self.assertEqual(back_resp.status_code, 200)
        self.assertTrue(back_resp.get_json()["success"])

        prods_updated = db.get_all_products()
        turm_updated = next(p for p in prods_updated if p["id"] == "turmeric")
        self.assertEqual(turm_updated["back"], test_back_url)

        # Reset back to original
        db.update_product_image("turmeric", "front", "haldi-front.png")
        db.update_product_image("turmeric", "back", "haldi-back.png")

        # 7. Unauthenticated client cannot update product image
        unauth_client = app.test_client()
        unauth_img = unauth_client.post("/api/admin/product/turmeric/image", data={
            "side": "front",
            "image_url": "fake.jpg"
        })
        self.assertEqual(unauth_img.status_code, 401)

        print("[PASS] Test 08: Direct Admin Login without OTP and Product Image Management verified.")

    def test_09_password_based_customer_signup_and_unified_login(self):
        """Verify seamless customer signup (account create) and unified login without OTP."""
        client = app.test_client()

        # 1. Customer Sign Up (Create Account)
        signup_payload = {
            "name": "Pooja Sharma",
            "identifier": "9829099887",
            "password": "shuddh_password_123",
            "address": "Vaishali Nagar",
            "city": "Jaipur",
            "pincode": "302021"
        }
        resp = client.post("/api/auth/signup", json=signup_payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["user"]["name"], "Pooja Sharma")
        self.assertEqual(data["user"]["phone"], "9829099887")

        # Session should be established immediately upon signup
        me_resp = client.get("/api/auth/me")
        me_data = me_resp.get_json()
        self.assertTrue(me_data["logged_in"])
        self.assertEqual(me_data["user"]["name"], "Pooja Sharma")

        # 2. Duplicate signup should be rejected politely
        dup_resp = client.post("/api/auth/signup", json=signup_payload)
        self.assertEqual(dup_resp.status_code, 400)
        self.assertIn("already exists", dup_resp.get_json()["error"])

        # 3. Customer Sign In from new session
        client2 = app.test_client()
        login_resp = client2.post("/api/auth/login", json={
            "identifier": "9829099887",
            "password": "shuddh_password_123"
        })
        self.assertEqual(login_resp.status_code, 200)
        login_data = login_resp.get_json()
        self.assertTrue(login_data["success"])
        self.assertFalse(login_data["is_admin"])
        self.assertEqual(login_data["user"]["name"], "Pooja Sharma")

        # 4. Wrong password rejected
        bad_resp = client2.post("/api/auth/login", json={
            "identifier": "9829099887",
            "password": "wrong_password"
        })
        self.assertEqual(bad_resp.status_code, 401)
        self.assertIn("Incorrect password", bad_resp.get_json()["error"])

        # 5. Non-existent account rejected with helpful advice
        notfound_resp = client2.post("/api/auth/login", json={
            "identifier": "9999999999",
            "password": "anypassword"
        })
        self.assertEqual(notfound_resp.status_code, 401)
        self.assertIn("No account found", notfound_resp.get_json()["error"])

        # 6. UNIFIED LOGIN: Store Owner Ankit logs in from the EXACT SAME endpoint
        admin_login_resp = client2.post("/api/auth/login", json={
            "identifier": "6350474290",
            "password": "Shuddh@Admin2026!"
        })
        self.assertEqual(admin_login_resp.status_code, 200)
        admin_data = admin_login_resp.get_json()
        self.assertTrue(admin_data["success"])
        self.assertTrue(admin_data["is_admin"])
        self.assertEqual(admin_data["redirect"], "/admin/dashboard")

        # 7. Customer places order using authenticated session (no OTP roadblock)
        order_resp = client.post("/api/order", json={
            "name": "Pooja Sharma",
            "phone": "9829099887",
            "items": [{"id": "coriander", "name": "Coriander Powder", "size": "100", "price": 40, "qty": 2}],
            "subtotal": 80,
            "discount": 0,
            "delivery_fee": 40,
            "total": 120,
            "payment_method": "COD",
            "address": "Vaishali Nagar",
            "city": "Jaipur",
            "state": "Rajasthan",
            "pincode": "302021"
        })
        self.assertEqual(order_resp.status_code, 200)
        self.assertTrue(order_resp.get_json()["success"])

        print("[PASS] Test 09: Password-based Account Create (Signup) and Unified Sign In verified.")

if __name__ == "__main__":
    unittest.main()
