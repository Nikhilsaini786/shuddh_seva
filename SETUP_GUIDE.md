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

## 🛡️ 5. Admin Authentication & Dashboard Security

### Admin Details:
- **Owner Name**: Ankit
- **Registered Mobile**: `+91 6350474290` (`6350474290`)
- **Registered Email**: `infosevaspice@gmail.com`
- **Default Master Password**: `Shuddh@Admin2026!` (configurable via `ADMIN_PASSWORD` in `.env`)

### 2-Step Authentication Flow:
1. Navigate to `/admin/login`.
2. Enter registered identifier (`infosevaspice@gmail.com` or `6350474290`) and your admin password.
3. Choose whether to receive the security OTP via **Email** or **SMS**.
4. The server validates credentials and dispatches a cryptographically secure 6-digit OTP.
5. Enter the OTP code. Upon verification, you are redirected to the protected dashboard at `/admin/dashboard`.

### Admin Dashboard Capabilities:
- **Store Owner Profile**: Displays Ankit's registered credentials and role.
- **Real-Time Feed**: Metrics for Total Revenue, Total Orders, Pending Orders, Delivered Orders, and Inquiries.
- **Order Pipeline**: Filter by `All Orders`, `Pending`, `Confirmed`, `Shipped`, `Delivered`, `Cancelled`. Update status with 1 click.
- **Customer Order History**: View all previous orders placed by any customer.
- **Product & Price Management Tab**: Edit selling prices, MRPs, and toggle In-Stock / Out-of-Stock for packaging pouches.
- **CSV Export & Invoices**: Download complete order spreadsheets and printable packing slips.

---

## 🧪 6. Running the Automated Test Suite

A comprehensive test suite is included in `test_system.py`:
- Test 01: Product Catalog & Pricing verification (100g, 200g, 500g, Combo).
- Test 02: 6-digit OTP generation, salted SHA-256 hashing, and 45s rate-limit cooldown.
- Test 03: Max 5 incorrect attempt limit and 5-minute expiry enforcement.
- Test 04: Customer authentication privacy (zero plain OTP leaks).
- Test 05: Mandatory customer login protection before checkout.
- Test 06: Order placement inserting into both `orders` and `order_items` tables.
- Test 07: Admin 2-step authentication, customer access block, and price management.

Run the test suite from PowerShell:
```powershell
python test_system.py
```
Expected output:
```text
Ran 7 tests in 0.408s
OK
[PASS] Test 01: Product Catalog & Prices verified accurately.
[PASS] Test 02: 6-digit OTP generation, hashing, and rate-limiting verified.
[PASS] Test 03: Maximum 5 incorrect attempt limit enforced correctly.
[PASS] Test 04: Customer Auth Endpoints & Session verified (no OTP leaks).
[PASS] Test 05: Mandatory customer login before checkout strictly enforced.
[PASS] Test 06: Order placed and line items stored in order_items successfully.
[PASS] Test 07: Admin 2-step authentication, access control, and price management verified.
```

---

## 🚀 7. Deploying to Vercel

The project includes `vercel.json` configured for Python serverless functions.

### Deploy via Vercel CLI:
```powershell
npx vercel
```
Follow the prompts to link your project and deploy.

### Deploy via GitHub:
1. Push your repository to GitHub.
2. In [Vercel Dashboard](https://vercel.com), click **Add New Project** → **Import Git Repository**.
3. Add your environment variables in Vercel Project Settings:
   - `SECRET_KEY`
   - `ADMIN_PASSWORD`
   - `SMTP_USER` & `SMTP_PASSWORD`
   - `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_PHONE_NUMBER`
4. Click **Deploy**!
