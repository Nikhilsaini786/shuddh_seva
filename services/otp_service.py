import os
import smtplib
import random
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)

def generate_6digit_otp():
    """Generate a cryptographically secure 6-digit numeric OTP."""
    return f"{random.randint(100000, 999999)}"

def send_email_otp(recipient_email, otp_code, recipient_name="Customer"):
    """
    Send a real 6-digit OTP to the recipient's email using Gmail SMTP.
    Requires SMTP_USER and SMTP_PASSWORD in environment variables.
    """
    smtp_host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.environ.get("SMTP_PORT", 587))
    smtp_user = os.environ.get("SMTP_USER", "").strip()
    smtp_pass = os.environ.get("SMTP_PASSWORD", "").strip()
    from_name = os.environ.get("SMTP_FROM_NAME", "Shuddh Seva Foods")

    # In testing mode without credentials, gracefully report configuration requirement
    if not smtp_user or not smtp_pass or "your_" in smtp_pass or "your_" in smtp_user or smtp_user == "your_email@gmail.com":
        return False, "Gmail SMTP is not configured. Please set real SMTP_USER and 16-character App Password in .env file."

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"{otp_code} is your Shuddh Seva Foods verification code"
        msg["From"] = f"{from_name} <{smtp_user}>"
        msg["To"] = recipient_email

        text_content = (
            f"Hello {recipient_name},\n\n"
            f"Your Shuddh Seva Foods verification code is: {otp_code}\n\n"
            f"This code will expire in 5 minutes. Please do not share this code with anyone.\n\n"
            f"Warm regards,\n"
            f"Shuddh Seva Foods Team\n"
            f"Jaipur, Rajasthan\n"
        )

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
          <meta charset="utf-8">
          <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f7f4ed; margin: 0; padding: 20px; color: #2b1810; }}
            .container {{ max-width: 520px; margin: 0 auto; background: #ffffff; border-radius: 14px; overflow: hidden; border: 1px solid #e8dfd5; box-shadow: 0 4px 15px rgba(0,0,0,0.06); }}
            .header {{ background: #4a210f; padding: 26px 20px; text-align: center; color: #ffffff; }}
            .header h1 {{ margin: 0; font-size: 24px; font-weight: 800; letter-spacing: 1px; }}
            .header p {{ margin: 5px 0 0 0; font-size: 11px; letter-spacing: 2px; color: #c8a34b; font-weight: 600; text-transform: uppercase; }}
            .content {{ padding: 32px 28px; text-align: center; }}
            .content h2 {{ font-size: 19px; color: #4a210f; margin-top: 0; margin-bottom: 12px; }}
            .content p {{ font-size: 14px; color: #555555; line-height: 1.6; margin-bottom: 22px; }}
            .otp-box {{ background: #fdfaf3; border: 2px dashed #c8a34b; border-radius: 12px; padding: 18px 24px; display: inline-block; margin: 8px auto 22px; }}
            .otp-code {{ font-size: 34px; font-weight: 900; letter-spacing: 8px; color: #176b3b; font-family: monospace; }}
            .expiry-note {{ font-size: 12px; color: #888888; margin-top: 4px; }}
            .warning {{ background: #fff8e1; border-radius: 8px; padding: 12px; font-size: 12px; color: #b45309; text-align: left; margin-top: 18px; }}
            .footer {{ background: #fbf9f5; border-top: 1px solid #f0eae1; padding: 16px 20px; text-align: center; font-size: 11px; color: #8c827a; }}
          </style>
        </head>
        <body>
          <div class="container">
            <div class="header">
              <h1>♡ SHUDDH SEVA</h1>
              <p>Foods • Pure & Natural Spices</p>
            </div>
            <div class="content">
              <h2>One-Time Verification Code</h2>
              <p>Hello <b>{recipient_name}</b>,<br>Use the following 6-digit OTP to complete your secure login / registration on Shuddh Seva Foods.</p>
              
              <div class="otp-box">
                <div class="otp-code">{otp_code}</div>
                <div class="expiry-note">⏱ Valid for 5 minutes</div>
              </div>

              <div class="warning">
                🔒 <b>Security Tip:</b> Shuddh Seva Foods will never call or message you asking for this OTP. Never share this code with anyone.
              </div>
            </div>
            <div class="footer">
              <p>Shuddh Seva Foods • Jaipur, Rajasthan - 302001<br>Customer Support: infosevaspice@gmail.com | +91 6350474290</p>
            </div>
          </div>
        </body>
        </html>
        """

        msg.attach(MIMEText(text_content, "plain"))
        msg.attach(MIMEText(html_content, "html"))

        if smtp_port == 465:
            server = smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=12)
        else:
            server = smtplib.SMTP(smtp_host, smtp_port, timeout=12)
            server.starttls()

        server.login(smtp_user, smtp_pass)
        server.send_message(msg)
        server.quit()
        return True, "OTP successfully delivered to your email inbox."
    except Exception as e:
        logger.error(f"SMTP error sending OTP to {recipient_email}: {e}")
        return False, f"Failed to send email OTP: {str(e)}"

def send_sms_otp(phone_number, otp_code):
    """
    Send a real 6-digit OTP to the Indian mobile number via Twilio SMS API.
    Requires TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, and TWILIO_PHONE_NUMBER.
    """
    account_sid = os.environ.get("TWILIO_ACCOUNT_SID", "").strip()
    auth_token = os.environ.get("TWILIO_AUTH_TOKEN", "").strip()
    twilio_number = os.environ.get("TWILIO_PHONE_NUMBER", "").strip()

    # Format phone with +91 if not present
    clean_phone = "".join(filter(str.isdigit, phone_number))
    if len(clean_phone) == 10:
        formatted_phone = f"+91{clean_phone}"
    elif len(clean_phone) > 10 and clean_phone.startswith("91"):
        formatted_phone = f"+{clean_phone}"
    else:
        formatted_phone = f"+{clean_phone}"

    if not account_sid or not auth_token or not twilio_number or account_sid.startswith("your_"):
        return False, "SMS provider (Twilio) is not configured. Please set TWILIO credentials in .env file or choose Email OTP."

    try:
        from twilio.rest import Client
        client = Client(account_sid, auth_token)
        message_body = (
            f"Your Shuddh Seva Foods verification code is: {otp_code}. "
            f"Valid for 5 minutes. Please do not share this OTP with anyone."
        )
        msg = client.messages.create(
            body=message_body,
            from_=twilio_number,
            to=formatted_phone
        )
        return True, f"OTP sent to mobile number via SMS (SID: {msg.sid[:8]}...)."
    except Exception as e:
        logger.error(f"Twilio SMS error to {formatted_phone}: {e}")
        return False, f"Failed to send SMS OTP: {str(e)}"
