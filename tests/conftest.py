# tests/conftest.py - Shared test configuration
import pytest
import tempfile
import os
from app import create_app, db
from app.models.db_models import User, Office, Enrollment, Resource, ChatSession, ChatMessage

@pytest.fixture(scope='function')
def app():
    """Create application for testing."""
    # Create a temporary database file
    db_fd, db_path = tempfile.mkstemp()
    
    app = create_app(testing=True)
    app.config.update({
        'TESTING': True,
        'SQLALCHEMY_DATABASE_URI': f'sqlite:///{db_path}',
        'WTF_CSRF_ENABLED': False,
        'SECRET_KEY': 'test-secret-key',
        'JWT_SECRET_KEY': 'test-jwt-secret'
    })

    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()

    os.close(db_fd)
    os.unlink(db_path)

@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()

@pytest.fixture
def runner(app):
    """Create test CLI runner."""
    return app.test_cli_runner()

# Fixture for test users
@pytest.fixture
def test_users(app):
    """Create test users."""
    with app.app_context():
        teacher = User(
            name="Test Teacher",
            email="teacher@test.com",
            password="hashed_password",  # In real app, this would be hashed
            role="teacher"
        )
        
        student = User(
            name="Test Student", 
            email="student@test.com",
            password="hashed_password",
            role="student"
        )
        
        db.session.add(teacher)
        db.session.add(student)
        db.session.commit()
        
        return {
            'teacher': teacher,
            'student': student
        }