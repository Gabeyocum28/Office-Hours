# tests/test_chat.py - Chat functionality tests  
import pytest
from unittest.mock import patch
from tests.utils import TestDataFactory, AuthHelper, OfficeHelper, ChatHelper

class TestChat:
    """Test chat functionality."""
    
    @pytest.fixture
    def setup_office_and_users(self, client):
        """Setup office with teacher and enrolled student."""
        # Create teacher and office
        office_setup = OfficeHelper.create_office_with_teacher(client)
        
        # Create student and enroll
        student_data = TestDataFactory.create_student()
        student_token = OfficeHelper.enroll_student(
            client, student_data, office_setup['join_code']
        )
        
        return {
            'teacher_token': office_setup['teacher_token'],
            'student_token': student_token,
            'office_id': office_setup['office_id']
        }
    
    def test_start_chat_session(self, client, setup_office_and_users):
        """Test starting a chat session."""
        data = setup_office_and_users
        
        response = client.post('/chat/start',
                             headers=AuthHelper.get_auth_headers(data["student_token"]),
                             json={'office_id': data['office_id']})
        
        assert response.status_code == 200
        json_data = response.get_json()
        assert 'session_id' in json_data
    
    def test_start_chat_unauthorized_office(self, client):
        """Test starting chat for unauthorized office fails."""
        # Create student not enrolled in any office
        student_data = TestDataFactory.create_student()
        token = AuthHelper.register_and_login(client, student_data)
        
        response = client.post('/chat/start',
                             headers=AuthHelper.get_auth_headers(token),
                             json={'office_id': 999})  # Non-existent office
        
        assert response.status_code == 403
    
    @patch('app.routes.chat.get_ai_response_with_context')
    def test_send_chat_message(self, mock_ai_response, client, setup_office_and_users):
        """Test sending a chat message."""
        mock_ai_response.return_value = "Hello! How can I help you today?"
        
        data = setup_office_and_users
        
        # Start chat session
        session_id = ChatHelper.start_chat_session(
            client, data["student_token"], data['office_id']
        )
        
        # Send message
        response = ChatHelper.send_message(
            client, data["student_token"], session_id, 'Hello AI!'
        )
        
        assert response.status_code == 200
        json_data = response.get_json()
        assert 'reply' in json_data
        assert json_data['reply'] == "Hello! How can I help you today?"
        
        # Verify AI function was called
        mock_ai_response.assert_called_once()
    
    def test_send_message_invalid_session(self, client, setup_office_and_users):
        """Test sending message with invalid session fails."""
        data = setup_office_and_users
        
        response = client.post('/chat/message',
                             headers=AuthHelper.get_auth_headers(data["student_token"]),
                             json={
                                 'session_id': 999,  # Invalid session
                                 'message': 'Hello!'
                             })
        
        assert response.status_code == 403
    
    def test_chat_history(self, client, setup_office_and_users):
        """Test retrieving chat history."""
        data = setup_office_and_users
        
        # Start chat and send message
        session_id = ChatHelper.start_chat_session(
            client, data["student_token"], data['office_id']
        )
        
        with patch('app.routes.chat.get_ai_response_with_context') as mock_ai:
            mock_ai.return_value = "Test response"
            ChatHelper.send_message(
                client, data["student_token"], session_id, 'Test message'
            )
        
        # Get history
        response = client.get(f'/chat/history/{session_id}',
                            headers=AuthHelper.get_auth_headers(data["student_token"]))
        
        assert response.status_code == 200
        json_data = response.get_json()
        assert 'history' in json_data
        assert len(json_data['history']) == 2  # User message + AI reply