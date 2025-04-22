from __future__ import annotations
import os
import time, pathlib, mimetypes, smtplib, cv2
from datetime import datetime
import RPi.GPIO as GPIO

#Email config
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT   = 587
EMAIL       = "alexv3796@gmail.com"
APP_PASS    = "wgfn arhj dxek evfg" # 16 digit Gmail App password Key
TO_EMAIL    = "alex.vasilev@gwmail.gwu.edu" #Users Email

#drive config
SERVICE_ACCOUNT_FILE = "/home/pi/service_key.json"
DRIVE_FOLDER_ID      = "1XJ55JpXqEhS_dwaen9UrUV7Kiar90UJ7"

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from typing import Optional

SCOPES = ["https://www.googleapis.com/auth/drive.file"]
CREDS  = service_account.Credentials.from_service_account_file(
            SERVICE_ACCOUNT_FILE, scopes=SCOPES)
DRIVE  = build("drive", "v3", credentials=CREDS, cache_discovery=False)


#email function
def send_email(subject: str, body: str, attachment_url: Optional[str] = None) -> None:

    msg  = f"Subject: {subject}\n\n{body}"
    if attachment_url:
        msg += f"\n\nClip link: {attachment_url}"
    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as s:
        s.starttls(); s.login(EMAIL, APP_PASS.replace(" ", ""))
        s.sendmail(EMAIL, TO_EMAIL, msg)
    print("✓  Email sent")

#upload to drive function
def drive_upload(local_path: str) -> str:
    """Upload file, give public‑link, return URL."""
    name = pathlib.Path(local_path).name
    ctype, _ = mimetypes.guess_type(local_path)
    media = MediaFileUpload(local_path, mimetype=ctype or "video/avi", resumable=True)

    file_meta = {"name": name, "parents": [DRIVE_FOLDER_ID]}
    uploaded  = DRIVE.files().create(
        body=file_meta, media_body=media, fields="id").execute()

#anyone can access the the drive with the link provided
    DRIVE.permissions().create(
        fileId=uploaded["id"],
        body={"role": "reader", "type": "anyone"},
        fields="id").execute()

    link = DRIVE.files().get(
        fileId=uploaded["id"], fields="webViewLink").execute()["webViewLink"]
    print(f"✓  Uploaded to Drive → {link}")
    return link


def record_video(duration=5, res=(1280, 720), fps=30) -> str | None:
    filename = f"/home/pi/security_clips/video_{datetime.now():%Y%m%d_%H%M%S}.avi"
    pathlib.Path(filename).parent.mkdir(exist_ok=True)

    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  res[0])
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, res[1])
    cap.set(cv2.CAP_PROP_FPS,          fps)

    if not cap.isOpened():
        print("✗  Camera error"); return None

    fourcc = cv2.VideoWriter_fourcc(*'XVID')
    out    = cv2.VideoWriter(filename, fourcc,
                             cap.get(cv2.CAP_PROP_FPS),
                             (int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
                              int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))))

    start = time.time()
    while (time.time() - start) < duration:
        ret, frame = cap.read()
        if not ret: break
        out.write(frame)
        time.sleep(0)
    cap.release(); out.release()
    os.chmod(filename, 0o644) 
    print(f"✓  Saved → {filename}")
    return filename


#motion sensor loop 
PIR_PIN, COOLDOWN = 17, 8
GPIO.setmode(GPIO.BCM); GPIO.setup(PIR_PIN, GPIO.IN)

print("Initialising PIR…"); time.sleep(2)
print("System armed (Ctrl‑C to quit)")

try:
    last = 0
    while True:
        if GPIO.input(PIR_PIN) and (time.time() - last) >= COOLDOWN:
            last = time.time()
            print("\n  Motion!")

            clip = record_video()
            if clip:
                url = drive_upload(clip)
                send_email(
                    "Home Security: Motion Detected",
                    f"Motion detected at {datetime.now():%Y-%m-%d %H:%M:%S}.",
                    attachment_url=url)
            time.sleep(0.5)
        time.sleep(0.1)

except KeyboardInterrupt:
    pass
finally:
    GPIO.cleanup()
    print("\nExiting…")
