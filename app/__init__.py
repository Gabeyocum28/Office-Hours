print("Loading app/__init__.py -- verify this is the file running")

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from flask_migrate import Migrate
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

db = SQLAlchemy()
jwt = JWTManager()
migrate = None  # Will initialize later

def create_app(testing=False):
    app = Flask(__name__)

    # Basic configuration with performance optimizations
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret-key")
    
    # Performance optimizations
    app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 31536000  # 1 year cache for static files
    app.config["PERMANENT_SESSION_LIFETIME"] = 1800  # 30 minutes session timeout
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SECURE"] = False  # Set to True in production with HTTPS
    app.config["WTF_CSRF_TIME_LIMIT"] = None  # Disable CSRF timeout for better UX
    
    if testing:
        # Use in-memory SQLite database for testing
        app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
        app.config["TESTING"] = True
        app.config["DEBUG"] = False
    else:
        app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///officehoursai.db"

    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # File upload configuration
    app.config["UPLOAD_FOLDER"] = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads")
    app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16MB max file size

    # JWT configuration
    app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET_KEY", "jwt-secret-key")

    # Initialize extensions with app and performance settings
    CORS(app, 
         origins=['http://localhost:5001', 'http://127.0.0.1:5001'],  # Specific origins for security
         supports_credentials=True,
         max_age=86400)  # Cache preflight requests for 24 hours
    
    db.init_app(app)
    jwt.init_app(app)

    global migrate
    migrate = Migrate(app, db)

    # Import blueprints inside factory
    from app.routes import auth, office, upload, chat

    # Register blueprints
    app.register_blueprint(auth.bp)
    app.register_blueprint(office.bp)
    app.register_blueprint(upload.bp)
    app.register_blueprint(chat.bp)

    print("Registered office blueprint:", office.bp.name)

    # Create database tables automatically (for test or dev)
    with app.app_context():
        db.create_all()

    return app
