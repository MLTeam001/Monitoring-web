import cv2
import os
import time
import threading
import queue
import requests
import numpy as np
from ultralytics import YOLO
from flask import Flask, Response

# ================= KONFIGURASI =================
MY_LAPTOP_IP = "10.10.10.5"   
UDP_PORT = "1234"
# Kurangi buffer internal FFmpeg
UDP_URL = f"udp://{MY_LAPTOP_IP}:{UDP_PORT}?overrun_nonfatal=1&fifo_size=50000"

# Tuning FFmpeg (Low Latency Flags)
os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "fflags;nobuffer|flags;low_delay"

SERVER_URL = "http://127.0.0.1:5000/api/update-camera" 
ROOM_NAME = "Ruang A"
CAMERA_TYPE = "door" 
LINE_X_POS = 0.5    
LINE_MARGIN = 30    

app = Flask(__name__)

# --- CLASS PENGHANCUR DELAY (WAJIB ADA) ---
class BufferlessVideoCapture:
    def __init__(self, name):
        self.cap = cv2.VideoCapture(name, cv2.CAP_FFMPEG)
        self.q = queue.Queue()
        self.t = threading.Thread(target=self._reader)
        self.t.daemon = True
        self.t.start()

    # Fungsi ini berjalan di background: SEDOT FRAME TERUS, BUANG YANG LAMA
    def _reader(self):
        while True:
            ret, frame = self.cap.read()
            if not ret:
                break
            if not self.q.empty():
                try:
                    self.q.get_nowait()   # Buang frame lama!
                except queue.Empty:
                    pass
            self.q.put(frame)             # Simpan frame terbaru

    def read(self):
        return self.q.get() # Berikan frame paling fresh ke AI

print(f"📡 Menunggu Stream UDP di {MY_LAPTOP_IP}:{UDP_PORT}...")
print("⏳ Loading AI Model...")
model = YOLO('yolov8n.pt') 

# MENGGUNAKAN CLASS BUFFERLESS (BUKAN cv2.VideoCapture BIASA)
cap = BufferlessVideoCapture(UDP_URL)

# Variabel Counter
entered_ids = set()
exited_ids = set()
track_history = {} 
count_in = 0  
count_out = 0 
last_send_time = 0

def generate_frames():
    global count_in, count_out, last_send_time, track_history
    
    while True:
        # Ambil frame TERBARU (Frame lama otomatis dibuang oleh Class di atas)
        frame = cap.read()
            
        # Resize biar enteng (480x360 sudah cukup jelas)
        frame = cv2.resize(frame, (480, 360))
        height, width = frame.shape[:2]
        line_pos = int(width * LINE_X_POS)
        
        # 1. AI Tracking
        results = model.track(frame, persist=True, classes=[0], verbose=False)
        
        # Visualisasi Garis
        if CAMERA_TYPE == 'door':
            cv2.line(frame, (line_pos, 0), (line_pos, height), (0, 0, 255), 2)
            cv2.line(frame, (line_pos - LINE_MARGIN, 0), (line_pos - LINE_MARGIN, height), (0, 255, 255), 1)
            cv2.line(frame, (line_pos + LINE_MARGIN, 0), (line_pos + LINE_MARGIN, height), (0, 255, 255), 1)

        if results[0].boxes.id is not None:
            boxes = results[0].boxes.xyxy.cpu()
            track_ids = results[0].boxes.id.int().cpu().tolist()

            current_ids = set(track_ids)
            track_history = {k: v for k, v in track_history.items() if k in current_ids}

            for box, track_id in zip(boxes, track_ids):
                x1, y1, x2, y2 = box
                cx = int((x1 + x2) / 2)
                cy = int(y2) 

                if CAMERA_TYPE == 'door':
                    if track_id in track_history:
                        prev_x = track_history[track_id]
                        if prev_x < line_pos and cx >= line_pos:
                            if track_id not in entered_ids:
                                entered_ids.add(track_id)
                                count_in += 1
                        elif prev_x > line_pos and cx <= line_pos:
                            if track_id not in exited_ids:
                                exited_ids.add(track_id)
                                count_out += 1
                    track_history[track_id] = cx

                color = (0, 255, 0)
                if track_id in entered_ids: 
                    cv2.line(frame, (line_pos, 0), (line_pos, height), (0, 255, 0), 4)
                
                cv2.rectangle(frame, (int(x1), int(y1)), (int(x2), int(y2)), color, 2)
                cv2.putText(frame, f"ID:{track_id}", (int(x1), int(y1)-10), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
        
        # Info Text
        cv2.putText(frame, f"IN: {count_in} | OUT: {count_out}", (10, 30), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)

        # Kirim Data ke API (Cepat, timeout pendek)
        if time.time() - last_send_time > 1.0:
            try:
                inside_count = max(0, count_in - count_out)
                payload = { "room_name": ROOM_NAME, "type": CAMERA_TYPE, "total_in": count_in, "total_out": count_out, "count": inside_count }
                requests.post(SERVER_URL, json=payload, timeout=0.05)
                last_send_time = time.time()
            except Exception: pass

        # Kompresi JPEG Agak Tinggi (60%) supaya streaming ke browser ngebut
        ret, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 60])
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')

@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

if __name__ == '__main__':
    print("🚀 Kamera Berjalan di http://127.0.0.1:5001")
    app.run(host='0.0.0.0', port=5001, debug=False, threaded=True)