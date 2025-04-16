# simple_email.py
import smtplib

# Configuration
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
EMAIL = "alexv3796@gmail.com"  # Your full Gmail address
APP_PASSWORD = "wgfn arhj dxek evfg"  # ← Paste your 16-digit app password here
TO_EMAIL = "alex.vasilev@gwmail.gwu.edu"

def send_email(subject, body):
    try:
        # Connect to server
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(EMAIL, APP_PASSWORD.replace(" ", ""))  # Remove spaces from app password
            
            # Send email
            message = f"Subject: {subject}\n\n{body}"
            server.sendmail(EMAIL, TO_EMAIL, message)
        
        print("Email sent successfully!")
        return True
    except Exception as e:
        print(f"Error sending email: {e}")
        return False

# Example usage
send_email(
    subject="Test from Raspberry Pi", 
    body="This is a test email sent from Python!"
)