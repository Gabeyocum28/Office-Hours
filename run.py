from app import create_app, db
from flask import Response, send_from_directory
import os

# Create the app using your factory
app = create_app()

# Add test frontend route - read file directly
@app.route('/')
def serve_test_frontend():
    try:
        file_path = os.path.join(os.getcwd(), 'test_frontend.html')
        with open(file_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
        return Response(html_content, mimetype='text/html')
    except Exception as e:
        return f"<h1>Error serving file:</h1><p>{str(e)}</p>"

@app.route('/test')
def test_endpoint():
    return {"message": "OfficeHours AI backend is running!", "status": "OK"}

# Add video chat route
@app.route('/video-chat')
def serve_video_chat():
    try:
        file_path = os.path.join(os.getcwd(), 'video_chat.html')
        with open(file_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
        return Response(html_content, mimetype='text/html')
    except Exception as e:
        return f"<h1>Video Chat Error:</h1><p>{str(e)}</p><p>Make sure video_chat.html is in your project root directory.</p>"

def init_app():
    # Create uploads directory if it doesn't exist
    upload_folder = app.config['UPLOAD_FOLDER']
    if not os.path.exists(upload_folder):
        os.makedirs(upload_folder)
    
    # Create database tables
    with app.app_context():
        db.create_all()

if __name__ == '__main__':
    init_app()
    
    print("🎓 Starting OfficeHours AI Development Server...")
    print(f"Current working directory: {os.getcwd()}")
    print("📚 Backend API: http://localhost:5001")
    print("🧪 Test Frontend: http://localhost:5001")
    print("🎥 Video Chat: http://localhost:5001/video-chat")
    print()
    print("Registered routes:")
    for rule in app.url_map.iter_rules():
        print(f"  {rule.methods} {rule} -> {rule.endpoint}")
    print()
    
    app.run(debug=True, port=5001)