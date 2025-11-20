from flask import Flask

def create_app():
    app = Flask(__name__)
    
    app.config['SECRET_KEY'] = 'temperature-monitor-2025'
    
    # Import dan daftarkan routes
    from app.routes import bp
    app.register_blueprint(bp)
    
    return app