from __future__ import annotations
import os, time, pathlib, mimetypes, smtplib, cv2, threading
from datetime import datetime
import RPi.GPIO as GPIO
from flask import Flask, Response
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from typing import Optional

# config
SMTP_SERVER, SMTP_PORT = "smtp.gmail.com", 587
EMAIL, APP_PASS        = "alexv3796@gmail.com", "wgfn arhj dxek evfg"
TO_EMAIL               = "alex.vasilev@gwmail.gwu.edu"
SERVICE_ACCOUNT_FILE   = "/home/pi/service_key.json"
DRIVE_FOLDER_ID        = "1XJ55JpXqEhS_dwaen9UrUV7Kiar90UJ7"

SCOPES = ["https://www.googleapis.com/auth/drive.file"]
CREDS  = service_account.Credentials.from_service_account_file(
            SERVICE_ACCOUNT_FILE, scopes=SCOPES)
DRIVE  = build("drive", "v3", credentials=CREDS, cache_discovery=False)

# flask live feed
app = Flask(__name__)
live_feed_active = True        

def generate_frames():
    """Yield MJPEG frames; fully releases camera while paused."""
    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    while True:
        # pause camera 
        if not live_feed_active:
            cap.release() # free the caamwra
            while not live_feed_active:
                time.sleep(0.05) # wait until resume
            cap = cv2.VideoCapture(0) # reopen
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
            continue
        # camera streaming
        ok, frame = cap.read()
        if not ok:
            break
        cv2.putText(frame, datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        ok, buf = cv2.imencode('.jpg', frame)
        if not ok:
            break
        yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n'
               + buf.tobytes() + b'\r\n')
    cap.release()

@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

def _run_flask():
    app.run(host='0.0.0.0', port=5000, threaded=True)

def start_video_stream():
    threading.Thread(target=_run_flask, daemon=True).start()
    print("✓ Live stream → http://172.20.10.4:5000/video_feed")

# email notification
def send_email(subject: str, body: str, attachment_url: Optional[str] = None):
    msg = f"Subject: {subject}\n\n{body}"
    if attachment_url:
        msg += f"\n\nClip link: {attachment_url}"
    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as s:
        s.starttls(); s.login(EMAIL, APP_PASS.replace(" ", ""))
        s.sendmail(EMAIL, TO_EMAIL, msg)
    print("✓ Email sent")

def drive_upload(path: str) -> str:
    name  = pathlib.Path(path).name
    ctype = mimetypes.guess_type(path)[0] or "video/avi"
    media = MediaFileUpload(path, mimetype=ctype, resumable=True)
    meta  = {"name": name, "parents": [DRIVE_FOLDER_ID]}

    file_id = DRIVE.files().create(body=meta, media_body=media,
                                   fields="id").execute()["id"]
    DRIVE.permissions().create(fileId=file_id,
                               body={"role": "reader", "type": "anyone"}).execute()
    link = DRIVE.files().get(fileId=file_id,
                             fields="webViewLink").execute()["webViewLink"]
    print(f"✓ Uploaded → {link}")
    return link

def record_video(duration=5, res=(1280, 720), fps=30) -> str | None:
    fname = f"/home/pi/security_clips/video_{datetime.now():%Y%m%d_%H%M%S}.avi"
    pathlib.Path(fname).parent.mkdir(exist_ok=True)

    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  res[0])
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, res[1])
    cap.set(cv2.CAP_PROP_FPS, fps)
    if not cap.isOpened():
        print("✗ Camera error"); return None

    fourcc = cv2.VideoWriter_fourcc(*'XVID')
    out    = cv2.VideoWriter(fname, fourcc, fps, res)

    start = time.time()
    while time.time() - start < duration:
        ok, frame = cap.read()
        if not ok: break
        out.write(frame)
    cap.release(); out.release()
    os.chmod(fname, 0o644)
    print(f"✓ Saved → {fname}")
    return fname

# PIR? motion sensor loop
PIR_PIN, COOLDOWN = 17, 8
GPIO.setmode(GPIO.BCM); GPIO.setup(PIR_PIN, GPIO.IN)
print("Initialising PIR…"); time.sleep(2)
print("System armed (Ctrl-C to quit)")

start_video_stream()

try:
    last = 0
    while True:
        if GPIO.input(PIR_PIN) and (time.time() - last) >= COOLDOWN:
            last = time.time()
            print("\n Motion!")

            live_feed_active = False # pause stream
            time.sleep(0.2) # give thread time to release cam
            clip = record_video() # camera is now  free
            live_feed_active = True # resume stream

            if clip:
                url = drive_upload(clip)
                folder = "https://drive.google.com/drive/folders/1XJ55JpXqEhS_dwaen9UrUV7Kiar90UJ7"
                send_email(
                        "Home Security: Motion Detected,
                        f"Motion at {datetime.now():%Y-%m-%d %H:%M:%S}\n\n"
                        f"Clip link: {url}\n"
                        f"All clips folder: {folder}"
                        f"View live feed via: http://172.20.10.4:5000/video_feed"
                )
                
            time.sleep(0.5)
        time.sleep(0.1)
except KeyboardInterrupt:
    pass
finally:
    live_feed_active = False
    GPIO.cleanup()
    print("\nExiting…")
