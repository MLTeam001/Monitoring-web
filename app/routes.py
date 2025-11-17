from flask import Blueprint, render_template, jsonify, request
from ml.temperature_model import temperature_model
from ml.data_processor import data_processor
import random
from datetime import datetime

bp = Blueprint('main', __name__)

# Data sementara (simulasi database)
rooms_data = {
    'Ruang A': {
        'capacity': 10,
        'current_people': [],
        'room_type': 'normal'
    },
    'Ruang B': {
        'capacity': 8,
        'current_people': [],
        'room_type': 'meeting'
    },
    'Ruang C': {
        'capacity': 12,
        'current_people': [],
        'room_type': 'ac'
    }
}

@bp.route('/')
def index():
    return render_template('index.html')

@bp.route('/dashboard')
def dashboard():
    # Hitung statistik
    total_people = sum(len(room['current_people']) for room in rooms_data.values())
    
    # Data untuk dashboard
    room_stats = []
    for room_name, room_data in rooms_data.items():
        if room_data['current_people']:
            temps = [p['suhu'] for p in room_data['current_people']]
            status, risk_score, analysis = temperature_model.analyze_room_health(temps)
        else:
            status = 'unknown'
            risk_score = 0
            analysis = {'average_temp': 0, 'max_temp': 0, 'min_temp': 0}
        
        room_stats.append({
            'name': room_name,
            'occupancy': len(room_data['current_people']),
            'capacity': room_data['capacity'],
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

@bp.route('/test-ml')
def test_ml():
    return render_template('test_ml.html')

# ===== API ROUTES =====

@bp.route('/api/add-person', methods=['POST'])
def add_person():
    """Tambah orang ke ruangan"""
    data = request.get_json()
    
    nama = data.get('nama', 'User')
    ruangan = data.get('ruangan', 'Ruang A')
    suhu = data.get('suhu', 36.5)
    
    # Validasi suhu
    if suhu < 20 or suhu > 45:
        return jsonify({
            'success': False,
            'message': 'Suhu tidak valid (harus antara 20-45°C)'
        }), 400
    
    # Predict status menggunakan ML
    room_type = rooms_data[ruangan]['room_type']
    prediction = temperature_model.predict_temperature_status(suhu, room_type)
    
    # Simpan data orang
    person_data = {
        'id': len(rooms_data[ruangan]['current_people']) + 1,
        'nama': nama,
        'suhu': suhu,
        'status': prediction['status'],
        'message': prediction['message'],
        'confidence': prediction['confidence'],
        'timestamp': datetime.now().strftime('%H:%M:%S')
    }
    
    # Tambahkan ke ruangan (maksimal capacity)
    if len(rooms_data[ruangan]['current_people']) < rooms_data[ruangan]['capacity']:
        rooms_data[ruangan]['current_people'].append(person_data)
        
        return jsonify({
            'success': True,
            'message': f'{nama} berhasil ditambahkan ke {ruangan}',
            'person': person_data,
            'room_occupancy': len(rooms_data[ruangan]['current_people'])
        })
    else:
        return jsonify({
            'success': False,
            'message': f'{ruangan} sudah penuh (kapasitas: {rooms_data[ruangan]["capacity"]})'
        }), 400

@bp.route('/api/room-status/<room_name>')
def get_room_status(room_name):
    """Get status ruangan"""
    room_data = rooms_data.get(room_name)
    
    if not room_data:
        return jsonify({'error': 'Ruangan tidak ditemukan'}), 404
    
    people = room_data['current_people']
    temperatures = [p['suhu'] for p in people]
    
    if temperatures:
        status, risk_score, analysis = temperature_model.analyze_room_health(temperatures)
        
        return jsonify({
            'room_name': room_name,
            'occupancy': len(people),
            'capacity': room_data['capacity'],
            'status': status,
            'risk_score': risk_score,
            'analysis': analysis,
            'people': people
        })
    else:
        return jsonify({
            'room_name': room_name,
            'occupancy': 0,
            'capacity': room_data['capacity'],
            'status': 'empty',
            'risk_score': 0,
            'analysis': {'message': 'Ruangan kosong'},
            'people': []
        })

@bp.route('/api/predict-temperature', methods=['POST'])
def predict_temperature():
    """Predict status suhu individual"""
    data = request.get_json()
    
    temperature = data.get('temperature', 36.5)
    room_type = data.get('room_type', 'normal')
    
    prediction = temperature_model.predict_temperature_status(temperature, room_type)
    
    return jsonify(prediction)

@bp.route('/api/clear-room/<room_name>', methods=['POST'])
def clear_room(room_name):
    """Kosongkan ruangan"""
    if room_name in rooms_data:
        rooms_data[room_name]['current_people'] = []
        return jsonify({
            'success': True,
            'message': f'{room_name} berhasil dikosongkan'
        })
    else:
        return jsonify({'error': 'Ruangan tidak ditemukan'}), 404

@bp.route('/api/simulate-data')
def simulate_data():
    """Generate data simulasi untuk testing"""
    names = ['Budi', 'Sari', 'Ahmad', 'Dewi', 'Rudi', 'Maya', 'Joko', 'Lina']
    rooms = list(rooms_data.keys())
    
    results = []
    
    for room in rooms:
        # Kosongkan dulu
        rooms_data[room]['current_people'] = []
        
        # Tambahkan 3-5 orang random
        n_people = random.randint(3, min(5, rooms_data[room]['capacity']))
        
        for i in range(n_people):
            nama = random.choice(names) + f" {i+1}"
            
            # Generate suhu berdasarkan tipe ruangan
            base_temp = 36.5
            if rooms_data[room]['room_type'] == 'meeting':
                base_temp += random.uniform(0.2, 0.6) 
            elif rooms_data[room]['room_type'] == 'ac':
                base_temp -= random.uniform(0.1, 0.3)  
                
            suhu = round(base_temp + random.uniform(-0.5, 0.5), 1)
            
            # 20% chance untuk suhu extreme
            if random.random() < 0.2:
                suhu = round(random.uniform(35.0, 38.5), 1)
            
            # Predict status
            prediction = temperature_model.predict_temperature_status(suhu, rooms_data[room]['room_type'])
            
            person_data = {
                'id': i + 1,
                'nama': nama,
                'suhu': suhu,
                'status': prediction['status'],
                'message': prediction['message'],
                'timestamp': datetime.now().strftime('%H:%M:%S')
            }
            
            rooms_data[room]['current_people'].append(person_data)
            results.append(f"{nama} di {room}: {suhu}°C ({prediction['status']})")
    
    return jsonify({
        'success': True,
        'message': f'Generated {sum(len(r["current_people"]) for r in rooms_data.values())} people',
        'details': results
    })