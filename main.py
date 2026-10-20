from ultralytics import YOLO
import cv2
import smtplib
import time
import serial
#import requests
#THINGSPEAK_API_KEY = "N7TDIQRHF9HM8JM9"

# ====================================
# SETTINGS
# ====================================
USE_HARDWARE = True
COM_PORT = 'COM11'   # change after checking Device Manager

# ====================================
# SERIAL SETUP (ESP32)
# ====================================
try:
    arduino = serial.Serial(COM_PORT, 115200)
    time.sleep(2)
    print("✅ ESP32 Connected")
except Exception as e:
    print("❌ Serial Error:", e)
    USE_HARDWARE = False

# ====================================
# EMAIL FUNCTION
# ====================================
def send_email():
    try:
        sender = "your maill id gmail.com"
        password = "your password"
        receiver = "your mail id"

        message = "Subject: ALERT!\n\nSuspicious activity detected!"

        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(sender, password)
        server.sendmail(sender, receiver, message)
        server.quit()

        print("📩 Email Sent")

    except Exception as e:
        print("❌ Email Error:", e)

# ====================================
# SAVE IMAGE
# ====================================
def save_image(frame):
    filename = f"alert_{int(time.time())}.jpg"
    cv2.imwrite(filename, frame)
    print("📸 Saved:", filename)


# ====================================
# THINGSPEAK FUNCTION
# ====================================
#def update_thingspeak(alert_value):
#    try:
#        url = "https://api.thingspeak.com/update"

#        data = {
#            "api_key": THINGSPEAK_API_KEY,
#            "field1": alert_value
#        }

#        requests.post(url, data=data)

#        print("☁️ ThingSpeak Updated")
#
#    except Exception as e:
#        print("ThingSpeak Error:", e)
        
 
#====================================
# LOAD YOLO MODEL
# ====================================
print("📦 Loading YOLO...")
model = YOLO("yolo11m.pt")
# ====================================
# CAMERA
# ====================================
cap = cv2.VideoCapture(0)
cap.set(3, 1280)
cap.set(4, 720)

# ====================================
# VARIABLES
# ====================================
prev_frame = None
motion_counter = 0
last_alert_time = 0

danger_objects = ["scissors"]

print("🚀 System Started")

# ====================================
# MAIN LOOP
# ====================================
while True:
    ret, frame = cap.read()
    if not ret:
        break

    alert = False
    person_detected = False
    weapon_detected = False
    bag_detected = False

    # ---------- MOTION ----------
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (21, 21), 0)

    if prev_frame is None:
        prev_frame = gray
        continue

    diff = cv2.absdiff(prev_frame, gray)
    _, thresh = cv2.threshold(diff, 25, 255, cv2.THRESH_BINARY)
    motion = cv2.countNonZero(thresh)

    motion_counter = motion_counter + 1 if motion > 20000 else max(0, motion_counter - 1)

    prev_frame = gray

    # ---------- YOLO ----------
    results = model(frame)

    for r in results:
        for box in r.boxes:
            cls = int(box.cls[0])
            label = model.names[cls]
            print(label)
            conf = float(box.conf[0])

            if label == "person":
                person_detected = True

            if label in danger_objects:
                weapon_detected = True

            if label in ["gun", "pistol", "rifle", "knife"]:
                weapon_detected = True

    # ---------- LOGIC ----------
    if person_detected and weapon_detected:
        alert = True

    if motion_counter > 15:
        alert = True

    if person_detected and bag_detected and motion_counter > 8:
        alert = True

    print("Person:", person_detected)
    print("Weapon:", weapon_detected)
    print("Alert:", alert)

       # ---------- ALERT ----------
    if alert and time.time() - last_alert_time > 5:

        print("🚨 ALERT!")

        #update_thingspeak(1)
        save_image(frame)
        send_email()

        # ESP32 SIGNAL
        if USE_HARDWARE:
            print("SENDING 1 TO ESP32")
            arduino.write(b'1\n')
        else:
            print("BUZZER ON (SIM)")

        last_alert_time = time.time()
        motion_counter = 0

    else:

        #update_thingspeak(0)

        if USE_HARDWARE:
            print("SENDING 0 TO ESP32")
            arduino.write(b'0\n')
    # ---------- DISPLAY ----------
    cv2.imshow("Smart Safety System", frame)

    if cv2.waitKey(1) == 27:
        break

cap.release()
cv2.destroyAllWindows()

if USE_HARDWARE:
    arduino.close()

print("System Stopped")
