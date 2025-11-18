from flask import Blueprint, render_template, jsonify, request
from ml.temperature_model import temperature_model
import random
from datetime import datetime

bp = Blueprint('main', __name__)

# --- STRUKTUR DATA UPDATE ---
rooms_data = {
    'Ruang A': {
        'capacity': 10,
        'door_in': 0,       # Total Masuk (Counter)
        'door_out': 0,      # Total Keluar (Counter)
        'inside_count': 0,  # Real-time Snapshot (Kamera Dalam)
        'current_people': [], 
        'room_type': 'normal',
        'last_update': None
    },
    'Ruang B': {
        'capacity': 8,
        'door_in': 0, 'door_out': 0, 'inside_count': 0,
        'current_people': [], 'room_type': 'meeting', 'last_update': None
    },
    'Ruang C': {
        'capacity': 12,
        'door_in': 0, 'door_out': 0, 'inside_count': 0,
        'current_people': [], 'room_type': 'ac', 'last_update': None
    }
}

@bp.route('/')
def index():
    return render_template('index.html')

@bp.route('/dashboard')
def dashboard():
    total_people = 0
    room_stats = []
    
    for room_name, data in rooms_data.items():
        # LOGIKA UTAMA:
        # Hitung Net Flow dari Pintu (Masuk - Keluar)
        door_net = max(0, data['door_in'] - data['door_out'])
        
        # Prioritas Data:
        # Jika kamera dalam mendeteksi orang, gunakan itu. 
        # Jika tidak (0), gunakan hitungan pintu.
        current_occupancy = data['inside_count'] if data['inside_count'] > 0 else door_net
        
        total_people += current_occupancy
        
        # Analisis Kesehatan Ruangan (Dummy Logic jika belum ada sensor suhu real)
        if data['current_people']:
            temps = [p['suhu'] for p in data['current_people']]
            status, risk_score, analysis = temperature_model.analyze_room_health(temps)
        else:
            status = 'normal'
            risk_score = 0
            analysis = {'average_temp': 0}

        room_stats.append({
            'name': room_name,
            'occupancy': current_occupancy,
            'door_net': door_net,      # Data Pintu
            'inside_val': data['inside_count'], # Data Kamera Dalam
            'capacity': data['capacity'],
            'status': status,
            'risk_score': risk_score,
            'avg_temp': analysis['average_temp']
        })
    
    return render_template('dashboard.html', 
                         room_stats=room_stats,
                         total_people=total_people)

@bp.route('/monitoring')
def monitoring():
    room_name = request.args.get('room', 'Ruang A')
    room_data = rooms_data.get(room_name, rooms_data['Ruang A'])
    
    return render_template('monitoring.html',
                         room_name=room_name,
                         room_data=room_data,
                         rooms_list=list(rooms_data.keys()))

@bp.route('/api/room-status/<room_name>')
def get_room_status(room_name):
    """API untuk monitoring.html mengambil data terbaru"""
    room_data = rooms_data.get(room_name)
    
    if not room_data:
        return jsonify({'error': 'Ruangan tidak ditemukan'}), 404
    
    # Logika Prioritas Occupancy
    door_net = max(0, room_data['door_in'] - room_data['door_out'])
    occupancy = room_data['inside_count'] if room_data['inside_count'] > 0 else door_net
    
    # Analisis Data (Suhu, dll)
    people = room_data['current_people']
    if people:
        temps = [p['suhu'] for p in people]
        status, risk_score, analysis = temperature_model.analyze_room_health(temps)
    else:
        status = 'normal'
        risk_score = 0
        analysis = {'average_temp': 0, 'message': 'Ruangan kosong'}

    # Tambahkan info detail pintu ke analisis agar bisa dibaca frontend
    analysis['door_in'] = room_data['door_in']
    analysis['door_out'] = room_data['door_out']

    return jsonify({
        'room_name': room_name,
        'occupancy': occupancy,
        'capacity': room_data['capacity'],
        'status': status,
        'risk_score': risk_score,
        'analysis': analysis,
        'people': people  # <--- INI KUNCINYA AGAR LIST ORANG MUNCUL
    })
    
@bp.route('/test-ml')
def test_ml():
    return render_template('test_ml.html')

# ===== API GATEWAY (Untuk Script Video/Raspberry Pi) =====

@bp.route('/api/update-camera', methods=['POST'])
def update_camera():
    """Endpoint penerima data dari video_tester.py"""
    data = request.get_json()
    room_name = data.get('room_name')
    
    if room_name not in rooms_data:
        return jsonify({'status': 'error', 'message': 'Room not found'}), 404
    
    room = rooms_data[room_name]
    room['last_update'] = datetime.now().strftime('%H:%M:%S')
    
    cam_type = data.get('type')
    
    if cam_type == 'door':
        # Update data counter pintu
        room['door_in'] = data.get('total_in', room['door_in'])
        room['door_out'] = data.get('total_out', room['door_out'])
        print(f"🚪 [DOOR] {room_name}: In={room['door_in']}, Out={room['door_out']}")
        
    elif cam_type == 'inside':
        # Update data real-time kamera dalam
        room['inside_count'] = data.get('count', 0)
        print(f"📷 [INSIDE] {room_name}: Detected={room['inside_count']}")
        
        # Karena video tester belum kirim suhu, kita buat dummy list orang
        # supaya tampilan monitoring tidak kosong
        _update_dummy_people_list(room, room['inside_count'])

    return jsonify({'status': 'success'})

def _update_dummy_people_list(room_data, count):
    """Helper: Generate data pengunjung dummy"""
    current_len = len(room_data['current_people'])
    
    if count > current_len:
        # Tambah orang baru
        for i in range(count - current_len):
            temp = round(random.uniform(36.0, 37.5), 1)
            pred = temperature_model.predict_temperature_status(temp, room_data['room_type'])
            room_data['current_people'].append({
                'id': random.randint(1000, 9999),
                'nama': f"Visitor {random.randint(1, 99)}",
                'suhu': temp,
                'status': pred['status'],
                'message': pred['message'],
                'timestamp': datetime.now().strftime('%H:%M:%S')
            })
    elif count < current_len:
        # Kurangi orang (FIFO - First In First Out logic sederhana)
        room_data['current_people'] = room_data['current_people'][:count]

# ===== API LAINNYA (Sama seperti sebelumnya) =====
# (Tetap pertahankan endpoint lain seperti add-person, clear-room, dll 
# agar fitur manual tetap jalan, tapi saya singkat disini biar tidak kepanjangan)

@bp.route('/api/clear-room/<room_name>', methods=['POST'])
def clear_room(room_name):
    if room_name in rooms_data:
        rooms_data[room_name]['current_people'] = []
        rooms_data[room_name]['door_in'] = 0
        rooms_data[room_name]['door_out'] = 0
        rooms_data[room_name]['inside_count'] = 0
        return jsonify({'success': True, 'message': 'Ruangan dikosongkan'})
    return jsonify({'error': 'Not found'}), 404

@bp.route('/api/simulate-data')
def simulate_data():
    # Reset endpoint simulasi agar kompatibel dengan struktur baru
    return jsonify({'success': True, 'message': 'Gunakan video_tester.py untuk simulasi!'})