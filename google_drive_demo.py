import RPi.GPIO as GPIO
import time
import cv2
from datetime import datetime
import smtplib
import os
from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive
import threading

# Configuration
PIR_PIN = 17
VIDEO_DURATION = 5  # seconds
RESOLUTION = (1280, 720)
FPS = 30

# Email configuration
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
EMAIL = "alexv3796@gmail.com"
APP_PASSWORD = "wgfn arhj dxek evfg"  # Remove spaces when using
TO_EMAIL = "alex.vasilev@gwmail.gwu.edu"
VIDEO_STORAGE_PATH = "/home/pi/security_videos/"
GOOGLE_DRIVE_FOLDER_ID = "1dcoj3GaLsmP3Js0o2Xum7v9IHXGEvD2C"  # Replace with your folder ID

# Initialize Google Drive
gauth = GoogleAuth()
drive = GoogleDrive(gauth)

def setup_gpio():
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(PIR_PIN, GPIO.IN)

def record_video(duration, resolution, fps):
    """Record video and return the filename"""
    if not os.path.exists(VIDEO_STORAGE_PATH):
        os.makedirs(VIDEO_STORAGE_PATH)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_file = os.path.join(VIDEO_STORAGE_PATH, f"motion_{timestamp}.avi")
    
    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, resolution[0])
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, resolution[1])
    cap.set(cv2.CAP_PROP_FPS, fps)
    
    if not cap.isOpened():
        print("Error: Could not open video device")
        return None
    
    actual_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    actual_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    actual_fps = cap.get(cv2.CAP_PROP_FPS)
    
    print(f"Recording at {actual_width}x{actual_height} at {actual_fps:.2f} fps")
    
    fourcc = cv2.VideoWriter_fourcc(*'XVID')
    out = cv2.VideoWriter(output_file, fourcc, actual_fps, (actual_width, actual_height))
    
    start_time = time.time()
    
    while (time.time() - start_time) < duration:
        ret, frame = cap.read()
        if not ret:
            print("Error: Could not read frame")
            break
        out.write(frame)
        print(f"Recording... {time.time() - start_time:.1f}/{duration} seconds", end='\r')
    
    cap.release()
    out.release()
    print(f"\nVideo saved as {output_file}")
    return output_file

def upload_to_drive(file_path):
    """Upload file to Google Drive and return shareable link"""
    try:
        # Create Google Drive file instance
        gfile = drive.CreateFile({'title': os.path.basename(file_path),
                                'parents': [{'id': GOOGLE_DRIVE_FOLDER_ID}]})
        
        # Set content and upload
        gfile.SetContentFile(file_path)
        gfile.Upload()
        
        # Make the file shareable and get link
        gfile.InsertPermission({
            'type': 'anyone',
            'value': 'anyone',
            'role': 'reader'
        })
        
        shareable_link = f"https://drive.google.com/file/d/{gfile['id']}/view?usp=sharing"
        print(f"Uploaded to Google Drive: {shareable_link}")
        
        return shareable_link
    except Exception as e:
        print(f"Error uploading to Google Drive: {e}")
        return None

def send_email(subject, body, video_link=None):
    """Send email with video link"""
    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(EMAIL, APP_PASSWORD.replace(" ", ""))
            
            message = f"Subject: {subject}\n\n{body}"
            if video_link:
                message += f"\n\nView the recorded video here: {video_link}"
            
            server.sendmail(EMAIL, TO_EMAIL, message)
        
        print("Email sent successfully!")
        return True
    except Exception as e:
        print(f"Error sending email: {e}")
        return False

def handle_motion_detection():
    """Handle the full motion detection workflow"""
    print("\nMotion detected! Starting recording...")
    time.sleep(0.5)  # Debounce
    
    # Record video
    video_file = record_video(VIDEO_DURATION, RESOLUTION, FPS)
    
    if video_file:
        # Upload to Google Drive
        video_link = upload_to_drive(video_file)
        
        if video_link:
            # Send email notification
            subject = "Security Alert: Motion Detected"
            body = f"Motion was detected at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}."
            send_email(subject, body, video_link)
        
        # Clean up local file after upload
        try:
            os.remove(video_file)
            print(f"Removed local file: {video_file}")
        except Exception as e:
            print(f"Error removing local file: {e}")

def main():
    setup_gpio()
    
    print("Initializing PIR sensor...")
    time.sleep(2)  # Let sensor settle
    print("System ready - waiting for motion...")
    
    try:
        while True:
            if GPIO.input(PIR_PIN):
                # Run motion handling in a thread to avoid blocking
                motion_thread = threading.Thread(target=handle_motion_detection)
                motion_thread.start()
                
                # Wait a bit before checking for motion again
                time.sleep(10)
            
            time.sleep(0.1)
    
    except KeyboardInterrupt:
        print("\nExiting...")
    finally:
        GPIO.cleanup()

if __name__ == "__main__":
    main()