from app import create_app

app = create_app()

if __name__ == '__main__':
    print("🚀 Temperature Monitoring System berjalan di: http://localhost:5000")
    print("📊 Dashboard: http://localhost:5000/dashboard")
    print("👥 Monitoring: http://localhost:5000/monitoring")
    print("🤖 Test ML: http://localhost:5000/test-ml")
    app.run(host='0.0.0.0', port=5000, debug=True)