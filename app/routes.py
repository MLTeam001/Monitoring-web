from flask import Blueprint, render_template, jsonify, request
from datetime import datetime, timedelta
import random

bp = Blueprint('main', __name__)

# --- KONFIGURASI RUANGAN ---
# Tambahkan 'stream_url' untuk setiap ruangan.
# Ganti IP (misal 192.168.1.105) sesuai dengan IP Raspberry Pi Anda.
rooms_data = {
    'Ruang A': { 
        'capacity': 10, 
        'stream_url': 'https://grvx4pf8-5001.asse.devtunnels.ms/video_feed',  # <--- URL Stream Raspi
        'door_in': 0, 
        'door_out': 0, 
        'inside_count': 0, 
        'status': 'available', 
        'last_update': None 
    },
    'Ruang B': { 
        'capacity': 8, 
        'stream_url': None, # Tidak ada kamera
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

@bp.route('/')
def index():
    return render_template('index.html')

@bp.route('/dashboard')
def dashboard():
    total_people = 0
    room_stats = []
    
    for room_name, data in rooms_data.items():
        door_net = max(0, data['door_in'] - data['door_out'])
        current_occupancy = data['inside_count'] if data['inside_count'] > 0 else door_net
        total_people += current_occupancy
        occupancy_pct = (current_occupancy / data['capacity']) * 100
        
        if current_occupancy >= data['capacity']:
            status = 'full'
        elif occupancy_pct >= 80:
            status = 'warning'
        else:
            status = 'normal'

        room_stats.append({
            'name': room_name,
            'stream_url': data.get('stream_url'), # Update dashboard juga agar konsisten
            'occupancy': current_occupancy,
            'door_net': door_net,
            'inside_val': data['inside_count'],
            'capacity': data['capacity'],
            'status': status,
            'percentage': int(occupancy_pct)
        })
    
    return render_template('dashboard.html', room_stats=room_stats, total_people=total_people)

@bp.route('/monitoring')
def monitoring():
    room_name = request.args.get('room', 'Ruang A')
    room_data = rooms_data.get(room_name, rooms_data['Ruang A'])
    
    total_people = 0
    room_stats = []
    
    for room_name_iter, data in rooms_data.items():
        door_net = max(0, data['door_in'] - data['door_out'])
        current_occupancy = data['inside_count'] if data['inside_count'] > 0 else door_net
        total_people += current_occupancy
        occupancy_pct = (current_occupancy / data['capacity']) * 100
        
        if current_occupancy >= data['capacity']:
            status = 'full'
        elif occupancy_pct >= 80:
            status = 'warning'
        else:
            status = 'normal'

        # Memasukkan data ke list stats
        room_stats.append({
            'name': room_name_iter,
            'stream_url': data.get('stream_url'), # <--- PENTING: Kirim URL Stream ke Template
            'occupancy': current_occupancy,
            'door_net': door_net,
            'inside_val': data['inside_count'],
            'capacity': data['capacity'],
            'status': status,
            'percentage': int(occupancy_pct)
        })
        
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

@bp.route('/api/room-status/<room_name>')
def get_room_status(room_name):
    room_data = rooms_data.get(room_name)
    if not room_data: return jsonify({'error': 'Not found'}), 404
    
    door_net = max(0, room_data['door_in'] - room_data['door_out'])
    occupancy = room_data['inside_count'] if room_data['inside_count'] > 0 else door_net
    
    if occupancy >= room_data['capacity']:
        status = 'full'; message = "⛔ RUANGAN PENUH"
    elif (occupancy / room_data['capacity']) >= 0.8:
        status = 'warning'; message = "⚠️ Hampir Penuh"
    else:
        status = 'normal'; message = "✅ Tersedia"

    return jsonify({
        'room_name': room_name, 
        'occupancy': occupancy, 
        'capacity': room_data['capacity'],
        'status': status, 
        'message': message, 
        'door_in': room_data['door_in'],
        'door_out': room_data['door_out'], 
        'inside_count': room_data['inside_count'],
        'stream_url': room_data.get('stream_url') # Opsional: kirim via API juga
    })

@bp.route('/api/update-camera', methods=['POST'])
def update_camera():
    data = request.get_json()
    room_name = data.get('room_name')
    if room_name in rooms_data:
        room = rooms_data[room_name]
        room['last_update'] = datetime.now().strftime('%H:%M:%S')
        if data.get('type') == 'door':
            room['door_in'] = data.get('total_in', 0)
            room['door_out'] = data.get('total_out', 0)
        elif data.get('type') == 'inside':
            room['inside_count'] = data.get('count', 0)
        return jsonify({'status': 'success'})
    return jsonify({'status': 'error'}), 404

@bp.route('/api/clear-room/<room_name>', methods=['POST'])
def clear_room(room_name):
    if room_name in rooms_data:
        rooms_data[room_name].update({'door_in':0, 'door_out':0, 'inside_count':0})
        return jsonify({'success': True})
    return jsonify({'error': 'Not found'}), 404