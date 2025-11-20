import numpy as np
import pandas as pd
from datetime import datetime
import os

class TemperatureModel:
    def __init__(self):
        self.model = None
        self.is_trained = False
        self.model_path = "ml/data/models/temperature_model.pkl"
        
    def initialize_model(self):
        """Initialize simple model rules"""
        print("🤖 Initializing Temperature Model...")
        self.is_trained = True
        print("✅ Model initialized with rule-based system")
        
    def predict_temperature_status(self, temperature, room_type="normal"):
        """
        Predict status berdasarkan suhu dan tipe ruangan
        """
        # Adjust thresholds berdasarkan tipe ruangan
        thresholds = self._get_thresholds(room_type)
        
        # Rule-based prediction
        if temperature < thresholds['danger_low'] or temperature > thresholds['danger_high']:
            status = "danger"
            confidence = 0.95
            if temperature < thresholds['danger_low']:
                message = f"🚨 SUHU TERLALU RENDAH! {temperature}°C"
            else:
                message = f"🚨 SUHU TERLALU TINGGI! {temperature}°C"
                
        elif (temperature < thresholds['warning_low'] or 
              temperature > thresholds['warning_high']):
            status = "warning"
            confidence = 0.85
            if temperature < thresholds['warning_low']:
                message = f"⚠️ Suhu mendekati batas bawah: {temperature}°C"
            else:
                message = f"⚠️ Suhu mendekati batas atas: {temperature}°C"
        else:
            status = "normal"
            confidence = 0.90
            message = f"✅ Suhu normal: {temperature}°C"
            
        return {
            'status': status,
            'confidence': confidence,
            'message': message,
            'temperature': temperature,
            'timestamp': datetime.now().strftime('%H:%M:%S')
        }
    
    def _get_thresholds(self, room_type):
        """Get thresholds berdasarkan tipe ruangan"""
        base_thresholds = {
            'danger_low': 36.0,
            'warning_low': 36.3,
            'warning_high': 37.2,
            'danger_high': 37.5
        }
        
        # Adjust untuk tipe ruangan berbeda
        adjustments = {
            'meeting': {'warning_high': 37.4, 'danger_high': 37.7},
            'ac': {'warning_low': 35.8, 'danger_low': 35.5},
            'normal': base_thresholds
        }
        
        return adjustments.get(room_type, base_thresholds)
    
    def analyze_room_health(self, temperature_readings):
        """
        Analisis kesehatan ruangan berdasarkan multiple readings
        """
        if not temperature_readings:
            return "unknown", 0, {"message": "No data available"}
            
        temps = np.array(temperature_readings)
        
        # Basic statistics
        analysis = {
            'average_temp': float(np.mean(temps)),
            'max_temp': float(np.max(temps)),
            'min_temp': float(np.min(temps)),
            'std_dev': float(np.std(temps)),
            'count': len(temps)
        }
        
        # Risk calculation
        risk_score = 0
        
        # Risk factors
        if analysis['max_temp'] > 37.5:
            risk_score += 40
        elif analysis['max_temp'] > 37.2:
            risk_score += 20
            
        if analysis['min_temp'] < 36.0:
            risk_score += 40
        elif analysis['min_temp'] < 36.3:
            risk_score += 20
            
        if analysis['std_dev'] > 0.8:
            risk_score += 20
            
        risk_score = min(risk_score, 100)
        
        # Determine overall status
        if risk_score >= 60:
            overall_status = "danger"
        elif risk_score >= 30:
            overall_status = "warning"
        else:
            overall_status = "normal"
            
        analysis['risk_score'] = risk_score
        analysis['overall_status'] = overall_status
        
        return overall_status, risk_score, analysis

# Global instance
temperature_model = TemperatureModel()
temperature_model.initialize_model()