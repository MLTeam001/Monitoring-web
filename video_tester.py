import cv2
from ultralytics import YOLO
import requests
import time

# ================= KONFIGURASI =================
VIDEO_PATH = "test.mp4"  # Ganti dengan nama file video Anda, atau 0 untuk Webcam
SERVER_URL = "http://localhost:5000/api/update-camera"

ROOM_NAME = "Ruang A"     # Target Ruangan
CAMERA_TYPE = "door"      # Mode: 'door' (Hitung In/Out) atau 'inside' (Hitung Total)

# Posisi Garis Pintu (Sesuaikan dengan Video Anda!)
LINE_Y_POS = 500
LINE_MARGIN = 20
# ===============================================

# Load AI
print("⏳ Loading YOLOv8 Model...")
model = YOLO('yolov8n.pt')

cap = cv2.VideoCapture(VIDEO_PATH)
if not cap.isOpened():
    print(f"❌ Error: Tidak bisa membuka video {VIDEO_PATH}")
    exit()

# Variabel Logic Counter
entered_ids = set()
exited_ids = set()
count_in = 0
count_out = 0
last_send_time = 0

print(f"🚀 Memulai Simulasi Kamera: Mode {CAMERA_TYPE.upper()}")
print("Tekan 'Q' untuk berhenti")

while True:
    success, frame = cap.read()
    if not success:
        print("Video selesai. Mengulang dari awal...")
        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
        continue

    frame = cv2.resize(frame, (1024, 600))

    # AI Tracking
    results = model.track(frame, persist=True, classes=[0], verbose=False)
    
    current_detected = 0
    
    if results[0].boxes.id is not None:
        boxes = results[0].boxes.xyxy.cpu()
        track_ids = results[0].boxes.id.int().cpu().tolist()
        
        current_detected = len(set(track_ids))

        if CAMERA_TYPE == 'door':
            cv2.line(frame, (0, LINE_Y_POS), (1024, LINE_Y_POS), (0, 255, 255), 2)

        for box, track_id in zip(boxes, track_ids):
            x1, y1, x2, y2 = box

            cx = int((x1 + x2) / 2)
            cy = int(y2)

            # Logika pintu
            if CAMERA_TYPE == 'door':
                if LINE_Y_POS - LINE_MARGIN < cy < LINE_Y_POS + LINE_MARGIN:
                    if cy > LINE_Y_POS: 
                        if track_id not in entered_ids:
                            entered_ids.add(track_id)
                            count_in += 1
                            print(f"⬇️ Masuk ID: {track_id}")
                    else:
                        if track_id not in exited_ids and count_in > count_out:
                            exited_ids.add(track_id)
                            count_out += 1
                            print(f"⬆️ Keluar ID: {track_id}")

            cv2.putText(frame, f"ID:{track_id}", (int(x1), int(y1)-10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,255,0), 2)
            cv2.rectangle(frame, (int(x1), int(y1)), (int(x2), int(y2)), (0,255,0), 2)

    # Kirim ke server
    if time.time() - last_send_time > 0.5:
        try:
            payload = {
                "room_name": ROOM_NAME,
                "type": CAMERA_TYPE
            }
            
            if CAMERA_TYPE == 'door':
                payload["total_in"] = count_in
                payload["total_out"] = count_out
            else:
                payload["count"] = current_detected

            requests.post(SERVER_URL, json=payload, timeout=0.1)
            last_send_time = time.time()
        except:
            pass

    # Tampilkan info
    status_text = (
        f"In: {count_in} | Out: {count_out}"
        if CAMERA_TYPE == "door"
        else f"People: {current_detected}"
    )
    cv2.putText(frame, status_text, (30, 50),
                cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)

    cv2.imshow("AI Monitoring Simulation", frame)

    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

cap.release()
cv2.destroyAllWindows()
