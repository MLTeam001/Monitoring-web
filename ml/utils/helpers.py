def format_temperature(temp, decimals=1):
    """Format suhu dengan jumlah decimal tertentu"""
    return f"{temp:.{decimals}f}°C"

def calculate_risk_level(temperature, room_capacity=10, current_occupancy=0):
    """
    Calculate risk level berdasarkan berbagai faktor
    """
    # Base risk dari suhu
    if temperature < 36.0 or temperature > 37.5:
        temp_risk = 80
    elif temperature < 36.3 or temperature > 37.2:
        temp_risk = 50
    else:
        temp_risk = 20
    
    # Risk dari occupancy
    occupancy_ratio = current_occupancy / room_capacity if room_capacity > 0 else 0
    if occupancy_ratio > 0.8:
        occupancy_risk = 60
    elif occupancy_ratio > 0.5:
        occupancy_risk = 30
    else:
        occupancy_risk = 10
    
    # Total risk score
    total_risk = (temp_risk * 0.7) + (occupancy_risk * 0.3)
    
    # Determine risk level
    if total_risk >= 70:
        risk_level = "critical"
    elif total_risk >= 50:
        risk_level = "high"
    elif total_risk >= 30:
        risk_level = "medium"
    else:
        risk_level = "low"
    
    return risk_level, int(total_risk)