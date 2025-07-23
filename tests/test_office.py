# tests/test_office.py - Office management tests
import pytest
from tests.utils import TestDataFactory, AuthHelper

class TestOffice:
    """Test office management endpoints."""
    
    def test_create_office_as_teacher(self, client):
        """Test teacher can create office."""
        # Register and login as teacher
        teacher_data = TestDataFactory.create_teacher()
        token = AuthHelper.register_and_login(client, teacher_data)
        
        # Create office
        office_data = {"name": "CS 101 Office Hours"}
        response = client.post('/office/create',
                             headers=AuthHelper.get_auth_headers(token),
                             json=office_data)
        
        assert response.status_code == 201
        json_data = response.get_json()
        assert 'office' in json_data
        assert json_data['office']['name'] == 'CS 101 Office Hours'
        assert 'join_code' in json_data['office']
    
    def test_create_office_as_student_fails(self, client):
        """Test student cannot create office."""
        # Register and login as student
        student_data = TestDataFactory.create_student()
        token = AuthHelper.register_and_login(client, student_data)
        
        # Try to create office
        office_data = {"name": "Unauthorized Office"}
        response = client.post('/office/create',
                             headers=AuthHelper.get_auth_headers(token),
                             json=office_data)
        
        assert response.status_code == 403
    
    def test_join_office_with_valid_code(self, client):
        """Test student can join office with valid code."""
        from tests.utils import OfficeHelper
        
        # Create teacher and office
        office_setup = OfficeHelper.create_office_with_teacher(client)
        
        # Create student
        student_data = TestDataFactory.create_student()
        student_token = AuthHelper.register_and_login(client, student_data)
        
        # Join office
        response = client.post('/office/join',
                             headers=AuthHelper.get_auth_headers(student_token),
                             json={"join_code": office_setup['join_code']})
        
        assert response.status_code in [200, 201]
    
    def test_join_office_with_invalid_code(self, client):
        """Test joining office with invalid code fails."""
        # Create student
        student_data = TestDataFactory.create_student()
        token = AuthHelper.register_and_login(client, student_data)
        
        # Try to join with invalid code
        response = client.post('/office/join',
                             headers=AuthHelper.get_auth_headers(token),
                             json={"join_code": "INVALID"})
        
        assert response.status_code == 404