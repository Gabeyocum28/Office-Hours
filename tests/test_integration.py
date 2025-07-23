# tests/test_integration.py - Full integration tests
import pytest
from unittest.mock import patch
from tests.utils import TestDataFactory, AuthHelper

class TestIntegration:
    """Test complete user flows."""
    
    @patch('app.routes.chat.get_ai_response_with_context')
    def test_complete_user_flow(self, mock_ai_response, client):
        """Test complete flow from registration to chat."""
        mock_ai_response.return_value = "I can help you with that!"
        
        # 1. Register teacher
        teacher_data = TestDataFactory.create_teacher(
            name="Professor Smith",
            email="prof@university.edu"
        )
        teacher_token = AuthHelper.register_and_login(client, teacher_data)
        
        # 2. Register student
        student_data = TestDataFactory.create_student(
            name="Alice Johnson", 
            email="alice@student.edu"
        )
        student_token = AuthHelper.register_and_login(client, student_data)
        
        # 3. Teacher creates office
        office_response = client.post('/office/create',
                                    headers=AuthHelper.get_auth_headers(teacher_token),
                                    json={"name": "Advanced Physics Office Hours"})
        assert office_response.status_code == 201
        office_data = office_response.get_json()['office']
        
        # 4. Student joins office
        join_response = client.post('/office/join',
                                  headers=AuthHelper.get_auth_headers(student_token),
                                  json={"join_code": office_data['join_code']})
        assert join_response.status_code in [200, 201]
        
        # 5. Student starts chat
        chat_start = client.post('/chat/start',
                               headers=AuthHelper.get_auth_headers(student_token),
                               json={'office_id': office_data['id']})
        assert chat_start.status_code == 200
        session_id = chat_start.get_json()['session_id']
        
        # 6. Student sends message
        message_response = client.post('/chat/message',
                                     headers=AuthHelper.get_auth_headers(student_token),
                                     json={
                                         'session_id': session_id,
                                         'message': 'Can you explain quantum mechanics?'
                                     })
        assert message_response.status_code == 200
        json_data = message_response.get_json()
        assert 'reply' in json_data
        assert json_data['reply'] == "I can help you with that!"
        
        # 7. Get chat history
        history_response = client.get(f'/chat/history/{session_id}',
                                    headers=AuthHelper.get_auth_headers(student_token))
        assert history_response.status_code == 200
        history_data = history_response.get_json()
        assert 'history' in history_data
        assert len(history_data['history']) == 2  # User message + AI reply
    
    def test_teacher_student_permissions(self, client):
        """Test that permissions are enforced correctly."""
        # Create teacher and student
        teacher_data = TestDataFactory.create_teacher()
        student_data = TestDataFactory.create_student()
        
        teacher_token = AuthHelper.register_and_login(client, teacher_data)
        student_token = AuthHelper.register_and_login(client, student_data)
        
        # Student tries to create office (should fail)
        response = client.post('/office/create',
                             headers=AuthHelper.get_auth_headers(student_token),
                             json={"name": "Unauthorized Office"})
        assert response.status_code == 403
        
        # Teacher creates office (should succeed)
        response = client.post('/office/create',
                             headers=AuthHelper.get_auth_headers(teacher_token),
                             json={"name": "Teacher's Office"})
        assert response.status_code == 201
        office_id = response.get_json()['office']['id']
        
        # Student tries to upload file (should fail)
        from tests.utils import FileHelper
        test_file = FileHelper.create_test_file("content", "test.txt")
        response = client.post('/upload/file',
                             headers=AuthHelper.get_auth_headers(student_token),
                             data={
                                 'office_id': office_id,
                                 'file': test_file
                             })
        assert response.status_code == 403