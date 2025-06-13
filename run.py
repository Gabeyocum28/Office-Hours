from app import app, db
import os

def init_app():
    # Create uploads directory if it doesn't exist
    upload_folder = app.config['UPLOAD_FOLDER']
    if not os.path.exists(upload_folder):
        os.makedirs(upload_folder)
    
    # Create database tables
    with app.app_context():
        db.create_all()

if __name__ == '__main__':
    for rule in app.url_map.iter_rules():
        print(f"{rule} -> {rule.endpoint}")
    app.run(debug=True, port=5001)
