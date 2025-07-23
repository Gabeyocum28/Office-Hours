# tests/test_auth.py - Authentication tests
import pytest
from app.models.db_models import User

class TestAuth:
    """Test authentication endpoints."""
    
    def test_register_student_success(self, client):
        """Test successful student registration."""
        data = {
            "name": "New Student",
            "email": "student@example.com", 
            "password": "securepass123",
            "role": "student"
        }
        
        response = client.post('/auth/register', json=data)
        assert response.status_code == 201
        
        json_data = response.get_json()
        assert json_data['message'] == 'User registered successfully'
    
    def test_register_teacher_success(self, client):
        """Test successful teacher registration."""
        data = {
            "name": "New Teacher",
            "email": "teacher@example.com",
            "password": "securepass123", 
            "role": "teacher"
        }
        
        response = client.post('/auth/register', json=data)
        assert response.status_code == 201
    
    def test_register_duplicate_email(self, client):
        """Test registration with duplicate email fails."""
        data = {
            "name": "Test User",
            "email": "duplicate@example.com",
            "password": "password123",
            "role": "student"
        }
        
        # Register first user
        response = client.post('/auth/register', json=data)
        assert response.status_code == 201
        
        # Try to register with same email
        response = client.post('/auth/register', json=data)
        assert response.status_code == 400
        
        json_data = response.get_json()
        assert 'already exists' in json_data['error']
    
    def test_register_missing_fields(self, client):
        """Test registration with missing fields fails."""
        data = {
            "name": "Test User",
            # Missing email, password, role
        }
        
        response = client.post('/auth/register', json=data)
        assert response.status_code == 400
        
        json_data = response.get_json()
        assert 'Missing required fields' in json_data['error']
    
    def test_login_success(self, client):
        """Test successful login."""
        # First register a user
        register_data = {
            "name": "Login Test User",
            "email": "login@example.com",
            "password": "testpass123",
            "role": "student"
        }
        client.post('/auth/register', json=register_data)
        
        # Then try to login
        login_data = {
            "email": "login@example.com",
            "password": "testpass123"
        }
        
        response = client.post('/auth/login', json=login_data)
        assert response.status_code == 200
        
        json_data = response.get_json()
        assert 'token' in json_data
        assert 'user' in json_data
        assert json_data['user']['email'] == 'login@example.com'
    
    def test_login_invalid_credentials(self, client):
        """Test login with invalid credentials fails."""
        login_data = {
            "email": "nonexistent@example.com",
            "password": "wrongpassword"
        }
        
        response = client.post('/auth/login', json=login_data)
        assert response.status_code == 401
        
        json_data = response.get_json()
        assert 'Invalid credentials' in json_data['error']