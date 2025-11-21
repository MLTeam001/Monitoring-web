# raspi_cam.py (Jalankan ini di Raspberry Pi)
import cv2
from ultralytics import YOLO
import requests
import time
from flask import Flask, Response

# ================= KONFIGURASI =================
# Ganti IP '192.168.1.X' dengan IP Laptop/PC server utama Anda
SERVER_URL = "http://192.168.1.X:5000/api/update-camera" 
ROOM_NAME = "Ruang A"
CAMERA_TYPE = "door"

# Posisi Garis Pintu (Sesuaikan dengan pandangan kamera Raspi)
LINE_Y_POS = 240    # Contoh: Setengah tinggi frame (jika resolusi 640x480)
LINE_MARGIN = 30    # Toleransi area garis

app = Flask(__name__)

# Load Model (Gunakan model nano 'n' agar ringan di Raspi)
print("⏳ Loading AI Model...")
model = YOLO('yolov8n.pt') 

# Buka Kamera (0 biasanya untuk kamera bawaan/USB pertama)
cap = cv2.VideoCapture(0) 
# Opsional: Turunkan resolusi agar FPS lancar di Raspi
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

# Variabel Global untuk Logika Counter
entered_ids = set()
exited_ids = set()
count_in = 0
count_out = 0
last_send_time = 0

def generate_frames():
    global count_in, count_out, last_send_time
    
    while True:
        success, frame = cap.read()
        if not success:
            break
            
        # 1. Proses AI YOLO (Tracking)
        # persist=True penting agar ID orang tetap sama antar frame
        results = model.track(frame, persist=True, classes=[0], verbose=False)
        
        # Gambar Garis Pintu (Untuk visualisasi saat setting posisi)
        if CAMERA_TYPE == 'door':
            cv2.line(frame, (0, LINE_Y_POS), (frame.shape[1], LINE_Y_POS), (0, 255, 255), 2)

        # Ambil data deteksi
        if results[0].boxes.id is not None:
            boxes = results[0].boxes.xyxy.cpu()
            track_ids = results[0].boxes.id.int().cpu().tolist()

            for box, track_id in zip(boxes, track_ids):
                x1, y1, x2, y2 = box
                # Titik tengah kaki (untuk referensi posisi)
                cx = int((x1 + x2) / 2)
                cy = int(y2)

                # === LOGIKA PINTU (Line Crossing) ===
                if CAMERA_TYPE == 'door':
                    # Cek apakah objek berada di area garis trigger
                    if LINE_Y_POS - LINE_MARGIN < cy < LINE_Y_POS + LINE_MARGIN:
                        # Logika sederhana: 
                        # Jika bergerak ke bawah (Y makin besar) = Masuk
                        if cy > LINE_Y_POS: 
                            if track_id not in entered_ids:
                                entered_ids.add(track_id)
                                count_in += 1
                                print(f"⬇️ Masuk ID: {track_id}")
                        # Jika bergerak ke atas (Y makin kecil) = Keluar
                        else:
                            if track_id not in exited_ids:
                                exited_ids.add(track_id)
                                count_out += 1
                                print(f"⬆️ Keluar ID: {track_id}")

                # Visualisasi Kotak & ID di Layar
                cv2.rectangle(frame, (int(x1), int(y1)), (int(x2), int(y2)), (0,255,0), 2)
                cv2.putText(frame, f"ID:{track_id}", (int(x1), int(y1)-10), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,255,0), 2)

        # Gambar hasil anotasi AI ke frame utama
        annotated_frame = results[0].plot()
        
        # Override frame dengan garis manual kita (opsional, agar garis kuning tetap terlihat jelas)
        if CAMERA_TYPE == 'door':
            cv2.line(annotated_frame, (0, LINE_Y_POS), (frame.shape[1], LINE_Y_POS), (0, 255, 255), 2)

        # 2. KIRIM DATA KE SERVER (Setiap 1 detik)
        if time.time() - last_send_time > 1.0:
            try:
                payload = {
                    "room_name": ROOM_NAME,
                    "type": CAMERA_TYPE,
                    "total_in": count_in,
                    "total_out": count_out
                }
                # Timeout kecil agar video tidak macet jika server down
                requests.post(SERVER_URL, json=payload, timeout=0.1)
                last_send_time = time.time()
            except Exception as e:
                pass # Abaikan error koneksi agar streaming tetap jalan

        # 3. Encode Frame ke JPEG untuk Streaming MJPEG
        ret, buffer = cv2.imencode('.jpg', annotated_frame)
        frame_bytes = buffer.tobytes()
        
        # Format standar Multipart untuk streaming video web
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

@app.route('/video_feed')
def video_feed():
    # Route ini yang akan dipanggil oleh tag <img> di HTML
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

if __name__ == '__main__':
    print(f"🚀 Kamera {ROOM_NAME} berjalan...")
    print(f"📡 Stream URL: http://0.0.0.0:5001/video_feed")
    
    # Host 0.0.0.0 wajib agar bisa diakses dari laptop lain dalam satu wifi
    app.run(host='0.0.0.0', port=5001, debug=False, threaded=True)