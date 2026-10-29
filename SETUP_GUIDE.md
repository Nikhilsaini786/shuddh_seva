# 🌿 Shuddh Seva Foods — Production Setup & Developer Guide

Complete documentation for the **Shuddh Seva Foods** e-commerce platform featuring **Real 6-Digit OTP Authentication (Twilio SMS & Gmail SMTP)** and a secure **Store Owner Admin Control Dashboard**.

---

## 📌 1. Project Overview & Architecture

- **Backend Framework**: Python 3.12+ / Flask 3.0+
- **Database**: SQLite 3 with WAL mode, parameterized queries, and auto-migration (`users`, `orders`, `order_items`, `products`, `otp_verifications`, `admin_users`, `inquiries`, `settings`).
- **Real OTP Security**:
  - Cryptographically generated 6-digit numeric OTPs.
  - Salted SHA-256 hash storage (`salt:target:otp`).
  - Strict 5-minute expiration.
  - Rate limiting: 45-second resend cooldown and 5 requests per hour.
  - Max 5 failed attempts per OTP before automatic invalidation.
  - Secrets and plain OTP codes are never exposed to frontend JavaScript or network responses.
- **Store Owner Admin**:
  - Name: **Ankit**
  - Registered Mobile: **+91 6350474290**
  - Registered Email: **infosevaspice@gmail.com**
  - Two-Step Authentication: Password + Security OTP delivered to Ankit's mobile or email.
- **Product Packaging & Pricing**:
  - **Red Chilli Powder**: 100g = ₹50 | 200g = ₹90 | 500g = ₹230
  - **Coriander Powder**: 100g = ₹40 | 200g = ₹80 | 500g = ₹180
  - **Turmeric Powder**: 100g = ₹50 | 200g = ₹90 | 500g = ₹210
  - **Kitchen Trio Combo (100g x 3)**: ₹140
  - Interactive **Front & Back packaging view** with zoom/inspection.
  - **Language switcher**: Seamless 1-click toggle between **English** and **हिंदी**.

---

## 💻 2. Step-by-Step VS Code Setup Instructions

### Step 2.1: Open Project in VS Code
1. Launch **Visual Studio Code**.
2. Click **File** → **Open Folder...**
3. Select the folder: `c:\Users\Nikhil Saini\Downloads\shuddh_seva`

### Step 2.2: Select Python Interpreter
1. Press `Ctrl + Shift + P` (or `Cmd + Shift + P` on Mac).
2. Type `Python: Select Interpreter` and hit **Enter**.
3. Select your installed Python 3.12 interpreter (e.g. `C:\Users\Nikhil Saini\Documents\python\python.exe`).

### Step 2.3: Install Dependencies
Open the integrated terminal (`Ctrl + \``) and run:
```powershell
pip install -r requirements.txt
```

### Step 2.4: Configure Environment Variables (.env)
A template file `.env.example` is provided in the project root. Copy it to `.env`:
```powershell
copy .env.example .env
```
Open `.env` and fill in your real provider credentials (see sections 3 & 4 below).

### Step 2.5: Initialize Database & Run Server
Run the Flask application:
```powershell
python app.py
```
Your local server will start at:
- 🛒 **Storefront**: [http://127.0.0.1:5006](http://127.0.0.1:5006)
- 🔐 **Customer Login / Signup**: [http://127.0.0.1:5006/login](http://127.0.0.1:5006/login)
- 🛡️ **Store Admin Login**: [http://127.0.0.1:5006/admin/login](http://127.0.0.1:5006/admin/login)
- 📊 **Admin Dashboard**: [http://127.0.0.1:5006/admin/dashboard](http://127.0.0.1:5006/admin/dashboard)

---

## ✉️ 3. Configuring Real Email OTP (Gmail SMTP)

To enable live delivery of 6-digit verification codes to customer and admin email addresses:

1. Open your Google Account: [https://myaccount.google.com/security](https://myaccount.google.com/security)
2. Ensure **2-Step Verification** is turned **ON**.
3. Under *2-Step Verification*, search for **App passwords**.
4. In the "App name" field, type: `Shuddh Seva Website` and click **Create**.
5. Google will generate a 16-character password (e.g. `abcd efgh ijkl mnop`).
6. Open your `.env` file and set:
   ```env
   SMTP_HOST=smtp.gmail.com
   SMTP_PORT=587
   SMTP_USER=infosevaspice@gmail.com
   SMTP_PASSWORD=abcdefghijklmnop
   SMTP_FROM_NAME=Shuddh Seva Foods
   ```
7. Save `.env`. The website will now send real, branded HTML verification emails!

---

## 📱 4. Configuring Real SMS OTP (Twilio)

To enable live delivery of 6-digit verification codes to customer and admin Indian mobile numbers:

1. Sign up or log in at [https://console.twilio.com](https://console.twilio.com).
2. Copy your **Account SID** and **Auth Token** from the dashboard.
3. Obtain an SMS-capable Twilio phone number (or alphanumeric sender ID for India DLT).
4. Open `.env` and configure:
   ```env
   TWILIO_ACCOUNT_SID=ACXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
   TWILIO_AUTH_TOKEN=your_auth_token_here
   TWILIO_PHONE_NUMBER=+1234567890
   ```
5. Save `.env`. All SMS OTP requests will automatically dispatch via Twilio API.

> **Note on Provider Credentials:**
> When credentials in `.env` are unconfigured or set to placeholders, the system safely detects it and returns a polite configuration notice without crashing or exposing fake codes.

---

## 🛡️ 5. Admin Authentication & Dashboard Control

### Admin Details:
- **Owner Name**: Ankit
- **Registered Mobile**: `+91 6350474290` (`6350474290`)
- **Registered Email**: `infosevaspice@gmail.com`
- **Default Master Password**: `Shuddh@Admin2026!` or `shuddh123` (configurable via `ADMIN_PASSWORD` in `.env`)

### Direct 1-Step Admin Login:
1. Navigate to `/admin/login` or click **👑 Admin Login** on the login page or navbar.
2. Enter identifier (`6350474290` or `infosevaspice@gmail.com` or `Ankit`) and password.
3. Click **Open Admin Dashboard 🚀** — you are directly logged in to `/admin/dashboard` without needing any extra OTP!
4. *(Optional: If Ankit logs in through the customer mobile/email OTP page, the system recognizes him as the store owner and provides a direct shortcut link to the Admin Dashboard).*

### Admin Dashboard Capabilities:
- **Product Packaging Image Uploads (Front & Back)**:
  - Both Front Packaging and Back Packaging are displayed side-by-side with previews.
  - Click **📷 Change Front** or **📷 Change Back** on any spice.
  - Upload a new image directly from your computer or phone, or paste an image URL.
  - The storefront updates automatically with 3D flip card support!
- **Product & Price Management Tab**:
  - Edit prices and MRPs for each pack size (100g, 200g, 500g).
  - 1-click In-Stock / Out-of-Stock toggle for all spice varieties.
- **Order Management & Tracking**:
  - Real-time customer orders with line-by-line item breakdown, quantities, prices, and payment mode (COD / UPI).
  - Instant order status updates (Pending, Confirmed, Shipped, Delivered, Cancelled).
  - 1-click WhatsApp customer chat button with pre-filled message.
  - Printable tax invoices / packing slips at `/admin/invoice/<order_id>`.
  - Customer lifetime order history.

---

## 🧪 6. Running the Automated Test Suite

A comprehensive test suite of 8 tests is included in `test_system.py`:
- Test 01: Product Catalog & Pricing verification (100g, 200g, 500g, Combo).
- Test 02: 6-digit OTP generation, salted SHA-256 hashing, and 45s rate-limit cooldown.
- Test 03: Max 5 incorrect attempt limit and 5-minute expiry enforcement.
- Test 04: Customer authentication privacy (zero plain OTP leaks).
- Test 05: Mandatory customer login protection before checkout.
- Test 06: Order placement inserting into both `orders` and `order_items` tables.
- Test 07: Admin authentication, customer access block, and price management.
- Test 08: Direct Admin Login without OTP, image uploads (front & back), and authorization.

Run the test suite from PowerShell:
```powershell
python test_system.py
```
Expected output:
```text
Ran 8 tests in 0.76s
OK
[PASS] Test 01: Product Catalog & Prices verified accurately.
[PASS] Test 02: 6-digit OTP generation, hashing, and rate-limiting verified.
[PASS] Test 03: Maximum 5 incorrect attempt limit enforced correctly.
[PASS] Test 04: Customer Auth Endpoints & Session verified (no OTP leaks).
[PASS] Test 05: Mandatory customer login before checkout strictly enforced.
[PASS] Test 06: Order placed and line items stored in order_items successfully.
[PASS] Test 07: Admin 2-step authentication, access control, and price management verified.
[PASS] Test 08: Direct Admin Login without OTP and Product Image Management verified.
```

---

## 🚀 7. Deploying to Vercel

The project is pre-configured for instant zero-config deployment on Vercel:
1. `vercel.json` routes all web and API requests to `app.py`.
2. **Serverless SQLite Compatibility**: `database.py` automatically initializes `/tmp/shuddh_seva.db` on cold starts and persists SQLite operations within the serverless environment.
3. **Session Cookie Stability**: A persistent `SECRET_KEY` fallback prevents session drops across Vercel serverless Lambda instances.
4. **Instant Verification Fallback**: On Vercel, if Twilio or SMTP credentials are not yet added, the system automatically provides an instant verification OTP so you and your customers can test signup, login, cart, and checkout seamlessly out of the box!
5. **Image Uploads on Vercel**: Uploaded images are stored directly in SQLite as base64 data URIs, so image changes persist without needing an external S3 bucket.

### Deploy via Vercel CLI:
```powershell
npx vercel
```
Follow the prompts to link your project and deploy.

### Deploy via GitHub:
1. Push your repository to GitHub (`git push origin main`).
2. In [Vercel Dashboard](https://vercel.com), click **Add New Project** → **Import Git Repository**.
3. (Optional) Set your real SMS / Email credentials in Vercel Project Settings → Environment Variables:
   - `ADMIN_PASSWORD` = `Shuddh@Admin2026!`
   - `SMTP_USER` & `SMTP_PASSWORD`
   - `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_PHONE_NUMBER`
4. Click **Deploy**!
