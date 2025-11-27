import cv2
from ultralytics import YOLO
import requests
import time
from flask import Flask, Response

# ================= KONFIGURASI =================
# Karena berjalan di laptop yang sama, kita pakai localhost (127.0.0.1)
SERVER_URL = "http://127.0.0.1:5000/api/update-camera" 
ROOM_NAME = "Ruang A"
CAMERA_TYPE = "door"  # Bisa ganti 'inside' jika ingin hitung total orang

# Posisi Garis (Nanti sesuaikan dengan webcam Anda)
LINE_Y_POS = 0.5    # 0.5 artinya posisi garis di tengah layar (50%)
LINE_MARGIN = 30    # Area toleransi deteksi

app = Flask(__name__)

print("⏳ Loading AI Model... (Akan sedikit berat di awal)")
model = YOLO('yolov8n.pt') 

# Buka Webcam Laptop (Index 0)
#cap = cv2.VideoCapture(0)
#menerima vidio dari raspberry pi
IP_RASPBERRY = "10.10.10.4" 
URL_STREAM = f"http://{IP_RASPBERRY}:5001/stream"

print(f"📡 Mencoba terhubung ke kamera Raspberry Pi di {URL_STREAM} ...")
cap = cv2.VideoCapture(URL_STREAM)

# Variabel Counter
entered_ids = set()
exited_ids = set()
count_in = 0
count_out = 0
last_send_time = 0

def generate_frames():
    global count_in, count_out, last_send_time, LINE_Y_POS
    
    while True:
        success, frame = cap.read()
        if not success:
            break
            
        # Resize agar tidak terlalu berat
        frame = cv2.resize(frame, (640, 480))
        height, width = frame.shape[:2]
        
        # Hitung posisi garis (pixel)
        line_pos = int(height * LINE_Y_POS)
        
        # 1. AI Tracking
        results = model.track(frame, persist=True, classes=[0], verbose=False)
        
        # Visualisasi Garis
        if CAMERA_TYPE == 'door':
            cv2.line(frame, (0, line_pos), (width, line_pos), (0, 255, 255), 2)

        # Logika Hitungan
        if results[0].boxes.id is not None:
            boxes = results[0].boxes.xyxy.cpu()
            track_ids = results[0].boxes.id.int().cpu().tolist()

            for box, track_id in zip(boxes, track_ids):
                x1, y1, x2, y2 = box
                cy = int(y2) # Titik kaki

                # Logic Keluar/Masuk
                if CAMERA_TYPE == 'door':
                    if line_pos - LINE_MARGIN < cy < line_pos + LINE_MARGIN:
                        if cy > line_pos: # Bergerak ke bawah
                            if track_id not in entered_ids:
                                entered_ids.add(track_id)
                                count_in += 1
                                print(f"⬇️ Masuk ID: {track_id}")
                        else: # Bergerak ke atas
                            if track_id not in exited_ids:
                                exited_ids.add(track_id)
                                count_out += 1
                                print(f"⬆️ Keluar ID: {track_id}")

                # Gambar Kotak & ID
                cv2.rectangle(frame, (int(x1), int(y1)), (int(x2), int(y2)), (0,255,0), 2)
                cv2.putText(frame, f"ID:{track_id}", (int(x1), int(y1)-10), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,255,0), 2)

        # Gambar hasil deteksi ke frame
        annotated_frame = results[0].plot()
        # Timpa garis kuning agar tetap terlihat jelas di atas anotasi AI
        if CAMERA_TYPE == 'door':
            cv2.line(annotated_frame, (0, line_pos), (width, line_pos), (0, 255, 255), 2)

        # 2. Kirim Data ke Dashboard (Setiap 1 detik)
        if time.time() - last_send_time > 1.0:
            try:
                payload = {
                    "room_name": ROOM_NAME,
                    "type": CAMERA_TYPE,
                    "total_in": count_in,
                    "total_out": count_out,
                    "count": len(entered_ids) - len(exited_ids) # Estimasi orang di dalam
                }
                requests.post(SERVER_URL, json=payload, timeout=0.1)
                last_send_time = time.time()
            except:
                pass # Abaikan jika server dashboard belum nyala

        # 3. Stream Video
        ret, buffer = cv2.imencode('.jpg', annotated_frame)
        frame_bytes = buffer.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

if __name__ == '__main__':
    # Jalankan di Port 5001 agar tidak bentrok dengan Web Utama (5000)
    print("🚀 Kamera Laptop Berjalan di http://127.0.0.1:5001")
    app.run(port=5001, debug=False, threaded=True)