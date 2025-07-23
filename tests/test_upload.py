# tests/test_upload.py - File upload tests
import pytest
import io
from unittest.mock import patch
from tests.utils import TestDataFactory, AuthHelper, OfficeHelper, FileHelper

class TestUpload:
    """Test file upload functionality."""
    
    @pytest.fixture
    def teacher_with_office(self, client):
        """Create teacher with office."""
        return OfficeHelper.create_office_with_teacher(client)
    
    @patch('app.utils.file_processor.extract_text_from_file')
    def test_upload_text_file(self, mock_extract_text, client, teacher_with_office):
        """Test uploading a text file."""
        mock_extract_text.return_value = "This is test content from the file."
        
        data = teacher_with_office
        
        response = FileHelper.upload_file(
            client, data["teacher_token"], data['office_id'], 
            filename="test.txt", content="Test file content"
        )
        
        assert response.status_code == 201
        json_data = response.get_json()
        assert 'resource' in json_data
        assert json_data['resource']['filename'] == 'test.txt'
    
    def test_upload_without_office_id(self, client, teacher_with_office):
        """Test upload without office_id fails."""
        data = teacher_with_office
        
        test_file = FileHelper.create_test_file("Test content", "test.txt")
        
        response = client.post('/upload/file',
                             headers=AuthHelper.get_auth_headers(data["teacher_token"]),
                             data={'file': test_file})
        
        assert response.status_code == 400
    
    def test_student_cannot_upload(self, client):
        """Test student cannot upload files."""
        # Create student
        student_data = TestDataFactory.create_student()
        token = AuthHelper.register_and_login(client, student_data)
        
        test_file = FileHelper.create_test_file("Test content", "test.txt")
        
        response = client.post('/upload/file',
                             headers=AuthHelper.get_auth_headers(token),
                             data={
                                 'office_id': 1,
                                 'file': test_file
                             })
        
        assert response.status_code == 403
    
    def test_get_office_files(self, client, teacher_with_office):
        """Test retrieving office files."""
        data = teacher_with_office
        
        # Upload a file first
        with patch('app.utils.file_processor.extract_text_from_file') as mock_extract:
            mock_extract.return_value = "Test content"
            FileHelper.upload_file(
                client, data["teacher_token"], data['office_id']
            )
        
        # Get files
        response = client.get(f'/upload/office/{data["office_id"]}/files',
                            headers=AuthHelper.get_auth_headers(data["teacher_token"]))
        
        assert response.status_code == 200
        json_data = response.get_json()
        assert 'files' in json_data
        assert len(json_data['files']) == 1