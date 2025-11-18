import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
import joblib
import os

class AnomalyDetector:
    def __init__(self):
        self.model = None
        self.scaler = StandardScaler()
        self.is_trained = False
        self.model_path = "ml/data/models/anomaly_detector.pkl"
        
    def train_model(self, temperature_data):
        """Train simple anomaly detection model"""
        print("🔄 Training Anomaly Detection Model...")
        
        # Convert to numpy array
        X = np.array(temperature_data).reshape(-1, 1)
        
        # Scale data
        X_scaled = self.scaler.fit_transform(X)
        
        # Train Isolation Forest
        self.model = IsolationForest(
            contamination=0.1,
            random_state=42,
            n_estimators=100
        )
        self.model.fit(X_scaled)
        
        self.is_trained = True
        
        # Save model
        os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
        joblib.dump(self.model, self.model_path)
        
        print("✅ Anomaly detection model trained and saved")
        
    def predict_anomaly(self, temperature):
        """Predict apakah suhu termasuk anomaly"""
        if not self.is_trained or self.model is None:
            return False, 0.0
            
        try:
            X = np.array([[temperature]])
            X_scaled = self.scaler.transform(X)
            
            prediction = self.model.predict(X_scaled)[0]
            anomaly_score = self.model.decision_function(X_scaled)[0]
            
            is_anomaly = (prediction == -1)
            
            return is_anomaly, float(anomaly_score)
            
        except Exception as e:
            print(f"❌ Prediction error: {e}")
            return False, 0.0

# Global instance
anomaly_detector = AnomalyDetector()