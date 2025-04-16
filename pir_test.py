# pir_test.py
import RPi.GPIO as GPIO
import time

PIR_PIN = 17

GPIO.setmode(GPIO.BCM)
GPIO.setup(PIR_PIN, GPIO.IN)

try:
    print("Testing PIR sensor (Ctrl+C to exit)")
    print("Waiting for sensor to settle...")
    time.sleep(2)  # Let sensor initialize
    print("Ready")
    
    while True:
        if GPIO.input(PIR_PIN):
            print("Motion detected!")
            time.sleep(0.5)  # Debounce
        time.sleep(0.1)
except KeyboardInterrupt:
    print("Exiting")
finally:
    GPIO.cleanup()