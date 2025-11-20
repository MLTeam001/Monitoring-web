import pandas as pd
import numpy as np
from datetime import datetime

class DataProcessor:
    def __init__(self):
        self.data = None
        
    def load_training_data(self, filepath="ml/data/training_data.csv"):
        """Load data training dari CSV"""
        try:
            self.data = pd.read_csv(filepath)
            print(f"✅ Loaded {len(self.data)} records from {filepath}")
            return self.data
        except FileNotFoundError:
            print("❌ Training data not found.")
            return None
    
    def preprocess_data(self, df):
        """Preprocess data untuk training"""
        if df is None:
            return None
            
        processed_df = df.copy()
        
        # Add features
        if 'timestamp' in processed_df.columns:
            processed_df['hour'] = pd.to_datetime(processed_df['timestamp']).dt.hour
            processed_df['day_of_week'] = pd.to_datetime(processed_df['timestamp']).dt.dayofweek
            processed_df['is_weekend'] = processed_df['day_of_week'].isin([5, 6]).astype(int)
        
        print("✅ Data preprocessing completed")
        return processed_df

# Global instance
data_processor = DataProcessor()