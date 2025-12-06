import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib
import os
import cv2
import numpy as np
import hailo
import threading
import queue
import time
import requests
from flask import Flask, Response
from pathlib import Path

from hailo_apps.hailo_app_python.core.common.buffer_utils import get_caps_from_pad, get_numpy_from_buffer
from hailo_apps.hailo_app_python.core.gstreamer.gstreamer_app import app_callback_class
from hailo_apps.hailo_app_python.apps.detection.detection_pipeline import GStreamerDetectionApp

# ================= KONFIGURASI =================
SERVER_URL = "http://192.168.1.19:5000/api/update-camera" # Pastikan IP Laptop benar
ROOM_NAME = "Ruang A"
CAMERA_TYPE = "door"
LINE_X_POS = 0.5    # Posisi garis (0.0 - 1.0)

# Inisialisasi Flask
flask_app = Flask(__name__)
output_frame = None
lock = threading.Lock()

# -----------------------------------------------------------------------------------------------
# Class User Data (Menyimpan State Counting & API)
# -----------------------------------------------------------------------------------------------
class user_app_callback_class(app_callback_class):
    def __init__(self):
        super().__init__()
        # State Counting
        self.entered_ids = set()
        self.exited_ids = set()
        self.track_history = {}
        self.count_in = 0
        self.count_out = 0
        self.last_send_time = 0
        
        # --- [BARU] Variabel untuk menyimpan jumlah orang real-time di layar ---
        self.current_visible_count = 0 

    def update_counts(self, frame_width, track_id, cx, line_pos_pixel):
        # Logika Line Crossing (Pintu)
        if CAMERA_TYPE == 'door':
            if track_id in self.track_history:
                prev_x = self.track_history[track_id]
                
                # Masuk (Kiri ke Kanan melewati garis)
                if prev_x < line_pos_pixel and cx >= line_pos_pixel:
                    if track_id not in self.entered_ids:
                        self.entered_ids.add(track_id)
                        self.count_in += 1
                
                # Keluar (Kanan ke Kiri melewati garis)
                elif prev_x > line_pos_pixel and cx <= line_pos_pixel:
                    if track_id not in self.exited_ids:
                        self.exited_ids.add(track_id)
                        self.count_out += 1
            
            # Update posisi terakhir
            self.track_history[track_id] = cx

    def send_api_data(self):
        # Kirim data setiap 1 detik
        if time.time() - self.last_send_time > 1.0:
            try:
                # --- [PERBAIKAN] ---
                # Jangan pakai (In - Out). Gunakan hitungan visual real-time
                real_time_count = self.current_visible_count

                payload = {
                    "room_name": ROOM_NAME,
                    "type": CAMERA_TYPE,
                    "total_in": self.count_in,
                    "total_out": self.count_out,
                    "count": real_time_count  # Kirim jumlah orang yang terlihat di layar
                }
                
                # Threading agar stream tidak putus saat kirim data
                threading.Thread(target=self._post_request, args=(payload,)).start()
                self.last_send_time = time.time()
            except Exception:
                pass

    def _post_request(self, payload):
        try:
            # Timeout singkat agar tidak nge-lag
            r = requests.post(SERVER_URL, json=payload, timeout=0.5)
            # Opsional: Print status untuk debug
            # print(f"Sent: {payload} | Status: {r.status_code}") 
        except Exception as e:
            print(f"Gagal kirim data: {e}")

# -----------------------------------------------------------------------------------------------
# Callback Function (Dipanggil setiap frame)
# -----------------------------------------------------------------------------------------------
def app_callback(pad, info, user_data):
    global output_frame, lock
    
    buffer = info.get_buffer()
    if buffer is None:
        return Gst.PadProbeReturn.OK

    user_data.increment()
    
    format, width, height = get_caps_from_pad(pad)
    frame = None
    if format is not None and width is not None and height is not None:
        frame = get_numpy_from_buffer(buffer, format, width, height)
    
    if frame is None:
        return Gst.PadProbeReturn.OK

    roi = hailo.get_roi_from_buffer(buffer)
    detections = roi.get_objects_typed(hailo.HAILO_DETECTION)

    # Setup garis
    line_pos_pixel = int(width * LINE_X_POS)
    cv2.line(frame, (line_pos_pixel, 0), (line_pos_pixel, height), (0, 0, 255), 2)

    current_ids = set()
    
    # --- [BARU] Reset hitungan visual setiap frame ---
    visible_people_now = 0 

    for detection in detections:
        label = detection.get_label()
        
        if label == "person":
            # --- [BARU] Tambah hitungan visual ---
            visible_people_now += 1
            
            bbox = detection.get_bbox()
            
            track_id = -1
            track = detection.get_objects_typed(hailo.HAILO_UNIQUE_ID)
            if len(track) == 1:
                track_id = track[0].get_id()
            
            if track_id != -1:
                current_ids.add(track_id)
                
                x1 = int(bbox.xmin() * width)
                y1 = int(bbox.ymin() * height)
                x2 = int(bbox.xmax() * width)
                y2 = int(bbox.ymax() * height)
                cx = int((x1 + x2) / 2)
                
                # Update logika Pintu (In/Out)
                user_data.update_counts(width, track_id, cx, line_pos_pixel)
                
                # Visualisasi Kotak & ID
                color = (0, 255, 0) # Hijau
                if track_id in user_data.entered_ids:
                    color = (255, 0, 0) # Biru jika sudah masuk
                
                cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                cv2.putText(frame, f"ID:{track_id}", (x1, y1-10), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

    # Bersihkan history
    user_data.track_history = {k: v for k, v in user_data.track_history.items() if k in current_ids}
    
    # --- [BARU] Update data user dengan jumlah visual saat ini ---
    user_data.current_visible_count = visible_people_now
    
    # Kirim API
    user_data.send_api_data()

    # Overlay Info di Layar Video
    # Menampilkan hitungan In/Out dan jumlah Real-time (Objek)
    #info_text = f"In: {user_data.count_in} | Out: {user_data.count_out} | Visual: {visible_people_now}"
    
    # Background hitam transparan untuk teks agar terbaca
    #cv2.rectangle(frame, (5, 5), (550, 50), (0, 0, 0), -1) 
    #cv2.putText(frame, info_text, (10, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2)

    frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
    
    with lock:
        output_frame = frame_bgr.copy()

    return Gst.PadProbeReturn.OK

# -----------------------------------------------------------------------------------------------
# Flask Streaming Functions
# -----------------------------------------------------------------------------------------------
def generate_frames():
    global output_frame, lock
    while True:
        with lock:
            if output_frame is None:
                continue
            ret, encoded_img = cv2.imencode('.jpg', output_frame, [int(cv2.IMWRITE_JPEG_QUALITY), 60])
            
        if not ret:
            continue
            
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + encoded_img.tobytes() + b'\r\n')
        time.sleep(0.03)

@flask_app.route('/video_feed')
def video_feed():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

def run_flask():
    flask_app.run(host='0.0.0.0', port=5001, debug=False, use_reloader=False)

if __name__ == "__main__":
    t = threading.Thread(target=run_flask)
    t.daemon = True
    t.start()
    
    print("🚀 Flask Camera Stream running on port 5001")
    
    project_root = Path(__file__).resolve().parent.parent
    os.environ["HAILO_ENV_FILE"] = str(project_root / ".env")
    
    user_data = user_app_callback_class()
    user_data.use_frame = True
    
    app = GStreamerDetectionApp(app_callback, user_data)
    app.run()
