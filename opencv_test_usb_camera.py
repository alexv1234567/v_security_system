import cv2
import time
from datetime import datetime

#Video settings
VIDEO_DURATION = 5 # seconds
RESOLUTION = (1280, 720)  # Logitech C270 camera at 720p
FPS = 30
OUTPUT_FILENAME = f"video_{datetime.now().strftime('%Y%m%d_%H%M%S')}.avi"

def record_video(duration, resolution, fps, output_file):
    #Initialize video capture
    cap = cv2.VideoCapture(0)
    
    #Set camera resolution
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, resolution[0])
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, resolution[1])
    cap.set(cv2.CAP_PROP_FPS, fps)
    
    #Check if camera opened successfully
    if not cap.isOpened():
        print("Error: Could not open video device")
        return
    
    #Get the actual resolution and fpss
    actual_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    actual_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    actual_fps = cap.get(cv2.CAP_PROP_FPS)
    
    print(f"Recording at {actual_width}x{actual_height} at {actual_fps:.2f} fps")
    print(f"Recording for {duration} seconds...")
    
    #Defining the codec
    fourcc = cv2.VideoWriter_fourcc(*'XVID')
    out = cv2.VideoWriter(output_file, fourcc, actual_fps, (actual_width, actual_height))
    
    start_time = time.time()
    
    while (time.time() - start_time) < duration:
        ret, frame = cap.read()
        if not ret:
            print("Error: Could not read frame")
            break
        
        #Write the frame to the output file
        out.write(frame)
        
        #To see if its working
        elapsed = time.time() - start_time
        print(f"Recording... {elapsed:.1f}/{duration} seconds", end='\r')
    
    #Release everything when done
    cap.release()
    out.release()
    print(f"\nVideo saved as {output_file}")

if __name__ == "__main__":
    record_video(VIDEO_DURATION, RESOLUTION, FPS, OUTPUT_FILENAME)
