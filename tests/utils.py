# tests/utils.py - Testing utilities and helpers

import jwt
import json
import tempfile
import os
from datetime import datetime, timedelta
from app.models.db_models import User, Office, Enrollment, Resource, ChatSession, ChatMessage
from app import db

class TestDataFactory:
    """Factory for creating test data."""
    
    @staticmethod
    def create_user(name="Test User", email="test@example.com", password="testpass", role="student"):
        """Create a test user."""
        return {
            "name": name,
            "email": email, 
            "password": password,
            "role": role
        }
    
    @staticmethod  
    def create_teacher(name="Test Teacher", email="teacher@example.com"):
        """Create a test teacher."""
        return TestDataFactory.create_user(name, email, "teacherpass", "teacher")
    
    @staticmethod
    def create_student(name="Test Student", email="student@example.com"):
        """Create a test student."""
        return TestDataFactory.create_user(name, email, "studentpass", "student")
    
    @staticmethod
    def create_office_data(name="Test Office"):
        """Create office data."""
        return {"name": name}

class AuthHelper:
    """Helper for authentication in tests."""
    
    @staticmethod
    def register_and_login(client, user_data):
        """Register user and return login token."""
        # Register
        register_response = client.post('/auth/register', json=user_data)
        assert register_response.status_code == 201
        
        # Login
        login_data = {
            "email": user_data["email"],
            "password": user_data["password"]
        }
        login_response = client.post('/auth/login', json=login_data)
        assert login_response.status_code == 200
        
        return login_response.get_json()['token']
    
    @staticmethod
    def get_auth_headers(token):
        """Get authorization headers."""
        return {'Authorization': f'Bearer {token}'}

class OfficeHelper:
    """Helper for office operations in tests."""
    
    @staticmethod
    def create_office_with_teacher(client, teacher_data=None, office_data=None):
        """Create office with teacher and return office info and token."""
        if teacher_data is None:
            teacher_data = TestDataFactory.create_teacher()
        if office_data is None:
            office_data = TestDataFactory.create_office_data()
        
        # Register and login teacher
        teacher_token = AuthHelper.register_and_login(client, teacher_data)
        
        # Create office
        office_response = client.post('/office/create',
                                    headers=AuthHelper.get_auth_headers(teacher_token),
                                    json=office_data)
        assert office_response.status_code == 201
        
        office_info = office_response.get_json()['office']
        
        return {
            'teacher_token': teacher_token,
            'office_id': office_info['id'],
            'join_code': office_info['join_code'],
            'office_info': office_info
        }
    
    @staticmethod
    def enroll_student(client, student_data, join_code):
        """Enroll student in office and return student token."""
        # Register and login student
        student_token = AuthHelper.register_and_login(client, student_data)
        
        # Join office
        join_response = client.post('/office/join',
                                  headers=AuthHelper.get_auth_headers(student_token),
                                  json={"join_code": join_code})
        assert join_response.status_code in [200, 201]
        
        return student_token

class ChatHelper:
    """Helper for chat operations in tests."""
    
    @staticmethod
    def start_chat_session(client, student_token, office_id):
        """Start chat session and return session ID."""
        response = client.post('/chat/start',
                             headers=AuthHelper.get_auth_headers(student_token),
                             json={'office_id': office_id})
        assert response.status_code == 200
        
        return response.get_json()['session_id']
    
    @staticmethod
    def send_message(client, student_token, session_id, message, use_avatar=False):
        """Send chat message and return response."""
        response = client.post('/chat/message',
                             headers=AuthHelper.get_auth_headers(student_token),
                             json={
                                 'session_id': session_id,
                                 'message': message,
                                 'use_avatar': use_avatar
                             })
        return response

class FileHelper:
    """Helper for file operations in tests."""
    
    @staticmethod
    def create_test_file(content="Test file content", filename="test.txt"):
        """Create a temporary test file."""
        import io
        return (io.BytesIO(content.encode()), filename)
    
    @staticmethod
    def upload_file(client, teacher_token, office_id, filename="test.txt", content="Test content"):
        """Upload a file and return response."""
        test_file = FileHelper.create_test_file(content, filename)
        
        response = client.post('/upload/file',
                             headers=AuthHelper.get_auth_headers(teacher_token),
                             data={
                                 'office_id': office_id,
                                 'file': test_file
                             })
        return response

class TestScenarios:
    """Common test scenarios that can be reused."""
    
    @staticmethod
    def setup_teacher_with_office(client):
        """Setup: Teacher with office created."""
        return OfficeHelper.create_office_with_teacher(client)
    
    @staticmethod
    def setup_teacher_student_office(client):
        """Setup: Teacher with office, student enrolled."""
        office_setup = OfficeHelper.create_office_with_teacher(client)
        
        student_data = TestDataFactory.create_student()
        student_token = OfficeHelper.enroll_student(
            client, student_data, office_setup['join_code']
        )
        
        return {
            **office_setup,
            'student_token': student_token
        }
    
    @staticmethod
    def setup_complete_chat_session(client):
        """Setup: Complete environment with active chat session."""
        setup = TestScenarios.setup_teacher_student_office(client)
        
        session_id = ChatHelper.start_chat_session(
            client, setup['student_token'], setup['office_id']
        )
        
        return {
            **setup,
            'session_id': session_id
        }