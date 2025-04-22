import smtplib

# Config
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
EMAIL = "alexv3796@gmail.com"  #full Gmail address
APP_PASSWORD = "wgfn arhj dxek evfg"  #16 digit password key
TO_EMAIL = "alex.vasilev@gwmail.gwu.edu"

def send_email(subject, body):
    try:
        #Connect to the server
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(EMAIL, APP_PASSWORD.replace(" ", ""))  #takes out spaces
            
            #Send email
            message = f"Subject: {subject}\n\n{body}"
            server.sendmail(EMAIL, TO_EMAIL, message)
        
        print("Email sent successfully!")
        return True
    except Exception as e:
        print(f"Error sending email: {e}")
        return False

#Case 1
send_email(
    subject="Test from Raspberry Pi", 
    body="This is a test email sent from Python!"
)
