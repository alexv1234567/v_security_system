from __future__ import annotations
import os, time, pathlib, mimetypes, smtplib, cv2, threading, numpy as np
from datetime import datetime
import RPi.GPIO as GPIO
from flask import Flask, Response
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from typing import Optional, List, Tuple

# config
SMTP_SERVER, SMTP_PORT = "smtp.gmail.com", 587
EMAIL, APP_PASS        = "alexv3796@gmail.com", "wgfn arhj dxek evfg"
TO_EMAIL               = "alexv3796@gmail.com"
SERVICE_ACCOUNT_FILE   = "/home/pi/service_key.json"
DRIVE_FOLDER_ID        = "1XJ55JpXqEhS_dwaen9UrUV7Kiar90UJ7"

SCOPES = ["https://www.googleapis.com/auth/drive.file"]
CREDS  = service_account.Credentials.from_service_account_file(
            SERVICE_ACCOUNT_FILE, scopes=SCOPES)
DRIVE  = build("drive", "v3", credentials=CREDS, cache_discovery=False)

# computer vision setup 
MODEL_PATH = os.path.expanduser("~/models")
try:
    HEAD_NET = cv2.dnn.readNetFromCaffe(
        os.path.join(MODEL_PATH, "deploy.prototxt"),
        os.path.join(MODEL_PATH, "res10_300x300_ssd_iter_140000.caffemodel"))
    HEAD_NET.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
    HEAD_NET.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)
except Exception as e:
    print(f"Error loading DNN model: {e}")
    HEAD_NET = None
    HAAR = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml")

# facial trackwer
def _make_tracker(): 
    if hasattr(cv2.legacy, 'TrackerCSRT_create'):
        return cv2.legacy.TrackerCSRT_create()
    if hasattr(cv2.legacy, 'TrackerKCF_create'):
        return cv2.legacy.TrackerKCF_create()
    if hasattr(cv2, 'TrackerCSRT_create'):
        return cv2.TrackerCSRT_create()
    if hasattr(cv2, 'TrackerKCF_create'):
        return cv2.TrackerKCF_create()
    return cv2.TrackerMOSSE_create()

MAX_LOST = 15  # frames allowed to be lost before a track is dropped 

class TrackedHead:
    """Wraps an OpenCV tracker and keeps the latest bounding box cached."""
    def __init__(self, bbox: Tuple[int, int, int, int], frame):
        self.tracker = _make_tracker()
        self.tracker.init(frame, tuple(bbox))
        self.bb   = tuple(bbox)  #cached (x,y,w,h)
        self.lost = 0

    def update(self, frame) -> Tuple[bool, Tuple[int, int, int, int]]:
        ok, bb = self.tracker.update(frame)
        if ok:
            self.bb = tuple(map(int, bb))
            self.lost = 0
        else:
            self.lost += 1
        return ok, self.bb

heads: List[TrackedHead] = []

def _is_overlap(box1, box2, thresh=0.5):
    x1, y1, w1, h1 = box1
    x2, y2, w2, h2 = box2
    xi1, yi1 = max(x1, x2), max(y1, y2)
    xi2, yi2 = min(x1+w1, x2+w2), min(y1+h1, y2+h2)
    inter = max(0, xi2 - xi1) * max(0, yi2 - yi1)
    union = w1*h1 + w2*h2 - inter
    return inter/union > thresh if union else False

def detect_and_track(frame):
    """Update trackers, run detection, draw red boxes."""
    global heads
    # updates the trackers
    kept = []
    for h in heads:
        ok, bb = h.update(frame)
        if ok or h.lost < MAX_LOST:
            kept.append(h)
        if ok:
            x, y, w, h_ = bb
            cv2.rectangle(frame, (x, y), (x+w, y+h_), (0, 0, 255), 2)
    heads = kept

    # periodoic detection
    if datetime.now().microsecond // 100000 < 1:
        detections = []
        if HEAD_NET is not None:
            H, W = frame.shape[:2]
            blob = cv2.dnn.blobFromImage(
                cv2.resize(frame, (300, 300)), 1.0,
                (300, 300), (104.0, 177.0, 123.0))
            HEAD_NET.setInput(blob)
            outs = HEAD_NET.forward()
            for i in range(outs.shape[2]):
                conf = outs[0, 0, i, 2]
                if conf > 0.5:
                    box = outs[0, 0, i, 3:7] * np.array([W, H, W, H])
                    x1, y1, x2, y2 = box.astype("int")
                    pad = int(min(x2-x1, y2-y1) * 0.2)
                    x1, y1 = max(0, x1-pad), max(0, y1-pad)
                    x2, y2 = min(W, x2+pad), min(H, y2+pad)
                    detections.append((x1, y1, x2-x1, y2-y1))
        else:  # Haar fallback
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            detections = [(x, y, w, h)
                          for (x, y, w, h) in HAAR.detectMultiScale(
                              gray, 1.1, 5, minSize=(60, 60))]

        for d in detections:
            if not any(_is_overlap(d, t.bb) for t in heads):
                try:
                    heads.append(TrackedHead(d, frame))
                    x, y, w, h_ = d
                    cv2.rectangle(frame, (x, y), (x+w, y+h_), (0, 0, 255), 2)
                except Exception as e:
                    print(f"Tracker init failed: {e}")
    return frame

# flask stream
app = Flask(__name__)
live_feed_active = True
cam_free = threading.Event()   
cam_free.set()

def generate_frames():
    global cam_free
    cap = cv2.VideoCapture(0)
    cam_free.clear()                           # camera is now busy 
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    while True:
        if not live_feed_active:
            cap.release()
            cam_free.set()                     # camera is now free 
            while not live_feed_active:
                time.sleep(0.05)
            cap = cv2.VideoCapture(0)
            cam_free.clear()                   # camera is now busy 
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
            continue

        ok, frame = cap.read()
        if not ok:
            break
        frame = detect_and_track(frame)
        cv2.putText(frame, datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        ok, buf = cv2.imencode('.jpg', frame,
                               [int(cv2.IMWRITE_JPEG_QUALITY), 80])
        if not ok:
            break
        yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n'
               + buf.tobytes() + b'\r\n')
    cap.release()
    cam_free.set()                             

@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

def _run_flask():
    app.run(host='0.0.0.0', port=5000, threaded=True)

def start_video_stream():
    threading.Thread(target=_run_flask, daemon=True).start()
    print("Live stream → http://172.20.10.4:5000/video_feed")

# email and google uoload/drive
def send_email(subject: str, body: str, attachment_url: Optional[str] = None):
    msg = f"Subject: {subject}\n\n{body}"
    if attachment_url:
        msg += f"\n\nClip link: {attachment_url}"
    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as s:
        s.starttls()
        s.login(EMAIL, APP_PASS.replace(" ", ""))
        s.sendmail(EMAIL, TO_EMAIL, msg)
    print("Email sent")

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
    print(f"Uploaded → {link}")
    return link

# video recording
def record_video(duration=5, res=(1280, 720), fps=30) -> str | None:
    cam_free.wait()        # must wait for the livestream to release the camera so no errors happens
    cam_free.clear()       # camera is busy during the recordig

    fname = f"/home/pi/security_clips/video_{datetime.now():%Y%m%d_%H%M%S}.avi"
    pathlib.Path(fname).parent.mkdir(exist_ok=True)
    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, res[0])
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, res[1])
    cap.set(cv2.CAP_PROP_FPS, fps)
    if not cap.isOpened():
        print("Camera error")
        cam_free.set()
        return None

    fourcc = cv2.VideoWriter_fourcc(*'XVID')
    out    = cv2.VideoWriter(fname, fourcc, fps, res)
    start  = time.time()
    while time.time() - start < duration:
        ok, frame = cap.read()
        if not ok:
            break
        frame = detect_and_track(frame)
        out.write(frame)
    cap.release()
    out.release()
    cam_free.set()          # allows for camera to be free after recording 
    os.chmod(fname, 0o644)
    print(f"Saved → {fname}")
    return fname

# pir motion sensor
PIR_PIN, COOLDOWN = 17, 8
GPIO.setmode(GPIO.BCM)
GPIO.setup(PIR_PIN, GPIO.IN)
print("Initialising PIR…")
time.sleep(2)
print("System armed (Ctrl-C to quit)")

start_video_stream()

try:
    last = 0.0
    while True:
        if GPIO.input(PIR_PIN) and (time.time() - last) >= COOLDOWN:
            last = time.time()
            print("\nMotion detected")

            live_feed_active = False
            clip = record_video()
            live_feed_active = True

            if clip:
                url = drive_upload(clip)
                folder = "https://drive.google.com/drive/folders/" + DRIVE_FOLDER_ID
                send_email(
                    "Home Security: Motion Detected",
                    (f"Motion at {datetime.now():%Y-%m-%d %H:%M:%S}\n\n"
                     f"Clip link: {url}\n"
                     f"All clips folder: {folder}\n"
                     f"View live feed via: http://172.20.10.4:5000/video_feed"))
            time.sleep(0.5)
        time.sleep(0.1)
except KeyboardInterrupt:
    pass
finally:
    live_feed_active = False
    GPIO.cleanup()
    print("\nSystem shutdown complete")
