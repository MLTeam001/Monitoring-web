from flask import Blueprint, render_template, jsonify, request, redirect, url_for
from datetime import datetime, timedelta
import random
import json
import os

bp = Blueprint('main', __name__)

# File untuk menyimpan data ruangan
ROOMS_FILE = 'rooms_data.json'

def load_rooms_data():
    """Memuat data ruangan dari file JSON"""
    if os.path.exists(ROOMS_FILE):
        with open(ROOMS_FILE, 'r') as f:
            data = json.load(f)
            # Konversi tipe data untuk memastikan konsistensi
            for room_name, room_data in data.items():
                room_data['capacity'] = int(room_data['capacity'])
                room_data['door_in'] = int(room_data.get('door_in', 0))
                room_data['door_out'] = int(room_data.get('door_out', 0))
                room_data['inside_count'] = int(room_data.get('inside_count', 0))
            return data
    else:
        # Data default jika file tidak ada
        default_rooms = {
            'Ruang A': { 
                'capacity': 10, 
                'stream_url': 'http://192.168.1.182:5001/video_feed',
                'door_in': 0, 
                'door_out': 0, 
                'inside_count': 0, 
                'status': 'available', 
                'last_update': None 
            },
            'Ruang B': { 
                'capacity': 8, 
                'stream_url': None,
                'door_in': 0, 
                'door_out': 0, 
                'inside_count': 0, 
                'status': 'available', 
                'last_update': None 
            },
            'Ruang C': { 
                'capacity': 12, 
                'stream_url': None,
                'door_in': 0, 
                'door_out': 0, 
                'inside_count': 0, 
                'status': 'available', 
                'last_update': None 
            }
        }
        save_rooms_data(default_rooms)
        return default_rooms

def save_rooms_data(rooms_data):
    """Menyimpan data ruangan ke file JSON"""
    with open(ROOMS_FILE, 'w') as f:
        json.dump(rooms_data, f, indent=4)

# Load data saat aplikasi start
rooms_data = load_rooms_data()

# --- HELPER: GENERATE DUMMY REPORT DATA ---
def format_stream_url(url):
    """Memformat IP/Host kamera menjadi URL lengkap dengan /video_feed"""
    if not url:
        return None
    
    url = url.strip()
    # Hapus whitespace di dalam (antisipasi copypaste kotor)
    url = "".join(url.split())
    
    if not url:
        return None
        
    # Pastikan diawali http
    if not url.startswith(('http://', 'https://')):
        url = 'http://' + url
        
    # Pastikan diakhiri /video_feed
    if not url.endswith('/video_feed'):
        # Hapus trailing slash jika ada sebelum menambah /video_feed
        url = url.rstrip('/') + '/video_feed'
        
    return url

def generate_monthly_data(room_name=None):
    """Membuat data palsu untuk laporan bulanan based on room if provided"""
    # Ambil data real-time untuk hari ini
    rooms_data_current = load_rooms_data()
    
    # Hitung statistik real-time hari ini
    today_visitors = 0
    today_occupancy_sum = 0
    today_alerts = 0
    room_count = 0
    
    if room_name and room_name in rooms_data_current:
        room = rooms_data_current[room_name]
        today_visitors = int(room.get('door_in', 0))
        cap = int(room.get('capacity', 10))
        occ = int(room.get('inside_count', 0)) if int(room.get('inside_count', 0)) > 0 else max(0, int(room.get('door_in', 0)) - int(room.get('door_out', 0)))
        today_occupancy_sum = (occ / cap * 100) if cap > 0 else 0
        today_alerts = 1 if today_occupancy_sum >= 80 else 0
        room_count = 1
        capacity_ref = cap
    else:
        for r_name, r_data in rooms_data_current.items():
            today_visitors += int(r_data.get('door_in', 0))
            cap = int(r_data.get('capacity', 10))
            occ = int(r_data.get('inside_count', 0)) if int(r_data.get('inside_count', 0)) > 0 else max(0, int(r_data.get('door_in', 0)) - int(r_data.get('door_out', 0)))
            today_occupancy_sum += (occ / cap * 100) if cap > 0 else 0
            if (occ / cap * 100) >= 80: today_alerts += 1
            room_count += 1
        capacity_ref = 100 # Multi-room context

    avg_occupancy_today = int(today_occupancy_sum / room_count) if room_count > 0 else 0
    
    data = []
    total_visitors = 0
    peak_day = {'date': '', 'count': 0}
    
    # Generate data untuk 30 hari terakhir
    today = datetime.now()
    for i in range(30):
        date = today - timedelta(days=29-i)
        date_str = date.strftime('%d %b')
        
        # Jika hari terakhir (hari ini), gunakan data real-time
        if i == 29:
            visitors = today_visitors
            occupancy_rate = avg_occupancy_today
            alerts = today_alerts
        else:
            # Random data pengunjung - scaled by capacity_ref for past days
            visitors = random.randint(int(capacity_ref * 2), int(capacity_ref * 8)) if room_name else random.randint(100, 500)
            occupancy_rate = random.randint(40, 95)
            alerts = random.randint(0, 3) if occupancy_rate > 85 else 0
        
        total_visitors += visitors
        
        if visitors >= peak_day['count']:
            peak_day = {'date': date_str, 'count': visitors}
            
        status = 'Normal'
        if occupancy_rate > 85: status = 'High'
        if occupancy_rate > 95: status = 'Critical'
        
        data.append({
            'date': date_str,
            'visitors': visitors,
            'avg_occupancy': occupancy_rate,
            'alerts': alerts,
            'status': status
        })
        
    # Safety Score Calculation: Basis 100%, dikurangi penalti jika ada alert hari ini
    # Di dunia nyata, ini akan dihitung dari rata-rata sejarah, namun di sini kita bikin dinamis
    base_safety = 100
    penalty = (today_alerts * 5) if room_name else (today_alerts * 2)
    safety_score = max(75, base_safety - penalty)
        
    return {
        'daily_logs': data,
        'summary': {
            'total_visitors': total_visitors,
            'avg_daily': int(total_visitors / 30),
            'peak_day': peak_day,
            'safety_score': safety_score
        }
    }

def calculate_room_stats():
    """Helper function untuk menghitung statistik ruangan"""
    total_people = 0
    room_stats = []
    
    for room_name, data in rooms_data.items():
        # Pastikan tipe data integer
        capacity = int(data['capacity'])
        door_in = int(data.get('door_in', 0))
        door_out = int(data.get('door_out', 0))
        inside_count = int(data.get('inside_count', 0))
        
        door_net = max(0, door_in - door_out)
        current_occupancy = inside_count if inside_count > 0 else door_net
        total_people += current_occupancy
        
        # Hindari division by zero
        if capacity > 0:
            occupancy_pct = (current_occupancy / capacity) * 100
        else:
            occupancy_pct = 0
        
        if current_occupancy >= capacity:
            status = 'full'
        elif occupancy_pct >= 80:
            status = 'warning'
        else:
            status = 'normal'

        room_stats.append({
            'name': room_name,
            'stream_url': data.get('stream_url'),
            'occupancy': current_occupancy,
            'door_net': door_net,
            'inside_val': inside_count,
            'capacity': capacity,
            'status': status,
            'percentage': int(occupancy_pct)
        })
    
    return total_people, room_stats

@bp.route('/')
def index():
    return render_template('index.html')

@bp.route('/dashboard')
def dashboard():
    total_people, room_stats = calculate_room_stats()
    return render_template('dashboard.html', room_stats=room_stats, total_people=total_people)

@bp.route('/monitoring')
def monitoring():
    room_name = request.args.get('room', list(rooms_data.keys())[0] if rooms_data else 'Ruang A')
    room_data = rooms_data.get(room_name)
    
    if not room_data:
        return redirect(url_for('main.dashboard'))
    
    total_people, room_stats = calculate_room_stats()
        
    return render_template('monitoring.html', 
                         room_name=room_name, 
                         room_data=room_data, 
                         rooms_list=list(rooms_data.keys()), 
                         room_stats=room_stats)

@bp.route('/reports')
def reports():
    """Halaman Laporan Bulanan"""
    selected_room = request.args.get('room')
    report_data = generate_monthly_data(selected_room)
    
    # Get all rooms for selector
    rooms_data = load_rooms_data()
    rooms_list = list(rooms_data.keys())
    
    return render_template('reports.html', 
                          data=report_data, 
                          rooms_list=rooms_list, 
                          selected_room=selected_room)

@bp.route('/room-management')
def room_management():
    """Halaman Manajemen Ruangan"""
    return render_template('room_management.html', rooms=rooms_data)

@bp.route('/add-room', methods=['POST'])
def add_room():
    """Endpoint untuk menambah ruangan baru (redirect ke dashboard)"""
    room_name = request.form.get('name')
    capacity = request.form.get('capacity', 10)
    stream_url = request.form.get('stream_url', '')
    
    if not room_name:
        # Jika gagal, tetap di halaman manajemen ruangan
        return redirect(url_for('main.room_management'))
    
    if room_name in rooms_data:
        # Jika ruangan sudah ada, tetap di halaman manajemen ruangan
        return redirect(url_for('main.room_management'))
    
    # Pastikan capacity bertipe integer
    try:
        capacity_int = int(capacity)
    except (ValueError, TypeError):
        capacity_int = 10  # Default value
    
    # Buat ruangan baru
    rooms_data[room_name] = {
        'capacity': capacity_int,
        'stream_url': format_stream_url(stream_url),
        'door_in': 0,
        'door_out': 0,
        'inside_count': 0,
        'status': 'available',
        'last_update': None
    }
    
    save_rooms_data(rooms_data)
    # Redirect ke dashboard setelah berhasil
    return redirect(url_for('main.dashboard'))

@bp.route('/api/room-status/<room_name>')
def get_room_status(room_name):
    room_data = rooms_data.get(room_name)
    if not room_data: 
        return jsonify({'error': 'Not found'}), 404
    
    # Pastikan tipe data integer
    capacity = int(room_data['capacity'])
    door_in = int(room_data.get('door_in', 0))
    door_out = int(room_data.get('door_out', 0))
    inside_count = int(room_data.get('inside_count', 0))
    
    # Hitung selisih bersih (Matematika Pintu)
    door_net = max(0, door_in - door_out)
    
    # Logika status utama
    occupancy = inside_count if inside_count > 0 else door_net
    
    if occupancy >= capacity:
        status = 'full'
        message = "CAPACITY REACHED"
    elif capacity > 0 and (occupancy / capacity) >= 0.8:
        status = 'warning'
        message = "LIMITED CAPACITY"
    else:
        status = 'normal'
        message = "ROOM AVAILABLE"

    return jsonify({
        'room_name': room_name, 
        'occupancy': occupancy, 
        'capacity': capacity,
        'status': status, 
        'message': message,
        
        # ✅ TAMBAHAN PENTING: Kirim hasil hitungan pintu ke web
        'door_net': door_net,  
        
        'door_in': door_in,
        'door_out': door_out, 
        'inside_count': inside_count,
        'stream_url': room_data.get('stream_url')
    })
@bp.route('/api/update-camera', methods=['POST'])
def update_camera():
    data = request.get_json()
    room_name = data.get('room_name')
    if room_name in rooms_data:
        room = rooms_data[room_name]
        room['last_update'] = datetime.now().strftime('%H:%M:%S')
        
        if data.get('type') == 'door':
            # Update data pintu
            room['door_in'] = int(data.get('total_in', 0))
            room['door_out'] = int(data.get('total_out', 0))
            
            # --- BAGIAN PENTING ---
            # Ambil 'count' langsung dari kiriman Raspberry Pi (Objek Visual)
            # Jangan dihitung manual (In - Out) di sini agar sesuai dengan kotak hijau
            if 'count' in data:
                room['inside_count'] = int(data['count'])
            else:
                # Fallback hanya jika tidak ada data count
                room['inside_count'] = max(0, room['door_in'] - room['door_out'])
            # ----------------------
            
        elif data.get('type') == 'inside':
            room['inside_count'] = int(data.get('count', 0))
        
        save_rooms_data(rooms_data)
        return jsonify({'status': 'success'})
    return jsonify({'status': 'error'}), 404

@bp.route('/api/clear-room/<room_name>', methods=['POST'])
def clear_room(room_name):
    if room_name in rooms_data:
        rooms_data[room_name].update({
            'door_in': 0, 
            'door_out': 0, 
            'inside_count': 0
        })
        save_rooms_data(rooms_data)
        return jsonify({'success': True})
    return jsonify({'error': 'Not found'}), 404

@bp.route('/api/edit-room/<room_name>', methods=['POST'])
def edit_room(room_name):
    """API untuk mengedit ruangan"""
    if room_name not in rooms_data:
        return jsonify({'error': 'Ruangan tidak ditemukan'}), 404
    
    data = request.get_json()
    
    # Update data ruangan dengan konversi tipe data
    if 'capacity' in data:
        try:
            rooms_data[room_name]['capacity'] = int(data['capacity'])
        except (ValueError, TypeError):
            return jsonify({'error': 'Kapasitas harus berupa angka'}), 400
            
    if 'stream_url' in data:
        rooms_data[room_name]['stream_url'] = format_stream_url(data['stream_url'])
        
    if 'manual_occupancy' in data:
        try:
            rooms_data[room_name]['inside_count'] = int(data['manual_occupancy'])
        except (ValueError, TypeError):
            return jsonify({'error': 'Occupancy harus berupa angka'}), 400
    
    save_rooms_data(rooms_data)
    return jsonify({'success': True, 'message': 'Ruangan berhasil diupdate'})

@bp.route('/api/delete-room/<room_name>', methods=['DELETE'])
def delete_room(room_name):
    """API untuk menghapus ruangan"""
    if room_name not in rooms_data:
        return jsonify({'error': 'Ruangan tidak ditemukan'}), 404
    
    del rooms_data[room_name]
    save_rooms_data(rooms_data)
    return jsonify({'success': True, 'message': 'Ruangan berhasil dihapus'})