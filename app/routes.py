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
def generate_monthly_data():
    """Membuat data palsu untuk laporan bulanan"""
    data = []
    total_visitors = 0
    peak_day = {'date': '', 'count': 0}
    
    # Generate data untuk 30 hari terakhir
    today = datetime.now()
    for i in range(30):
        date = today - timedelta(days=29-i)
        date_str = date.strftime('%d %b')
        
        # Random data pengunjung
        visitors = random.randint(50, 200)
        occupancy_rate = random.randint(40, 95)
        alerts = random.randint(0, 5)
        
        total_visitors += visitors
        
        if visitors > peak_day['count']:
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
        
    return {
        'daily_logs': data,
        'summary': {
            'total_visitors': total_visitors,
            'avg_daily': int(total_visitors / 30),
            'peak_day': peak_day,
            'safety_score': 98 - random.randint(0, 5)
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
    report_data = generate_monthly_data()
    return render_template('reports.html', data=report_data)

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
        'stream_url': stream_url if stream_url else None,
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
        message = "⛔ RUANGAN PENUH"
    elif capacity > 0 and (occupancy / capacity) >= 0.8:
        status = 'warning'
        message = "⚠️ Hampir Penuh"
    else:
        status = 'normal'
        message = "✅ Tersedia"

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
        rooms_data[room_name]['stream_url'] = data['stream_url']
        
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