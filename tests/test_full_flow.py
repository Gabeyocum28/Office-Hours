import pytest
from app import create_app, db
from unittest.mock import patch
from app.models.db_models import Enrollment, User

@pytest.fixture
def client():
    app = create_app(testing=True)

    with app.app_context():
        # Drop all tables and recreate them fresh
        db.drop_all()
        db.create_all()

    with app.test_client() as client:
        yield client


def test_full_flow(client):
    # Register student
    student_data = {
        "name": "student1",
        "email": "student1@example.com",
        "password": "studentpass",
        "role": "student"
    }
    res = client.post('/auth/register', json=student_data)
    assert res.status_code == 201

    # Try to get student user id from response (optional)
    student_user_id = res.json.get('user', {}).get('id')
    if not student_user_id:
        # Query DB to get student user id
        with client.application.app_context():
            student_user = User.query.filter_by(email=student_data['email']).first()
            student_user_id = student_user.id

    # Register teacher
    teacher_data = {
        "name": "teacher1",
        "email": "teacher1@example.com",
        "password": "teacherpass",
        "role": "teacher"
    }
    res = client.post('/auth/register', json=teacher_data)
    assert res.status_code == 201

    # Duplicate registration fails
    res = client.post('/auth/register', json=teacher_data)
    assert res.status_code == 400

    # Login student
    student_login = {
        "email": "student1@example.com",
        "password": "studentpass"
    }
    res = client.post('/auth/login', json=student_login)
    assert res.status_code == 200
    student_token = res.json['token']

    # Login teacher
    teacher_login = {
        "email": "teacher1@example.com",
        "password": "teacherpass"
    }
    res = client.post('/auth/login', json=teacher_login)
    assert res.status_code == 200
    teacher_token = res.json['token']

    # Teacher creates office
    office_data = {
        "name": "Math 101",
        "description": "Office hours for Math 101",  # Ignored if your endpoint doesn't use it
    }
    res = client.post('/office/create',
                      headers={'Authorization': f'Bearer {teacher_token}'},
                      json=office_data)
    assert res.status_code == 201

    join_code = res.json['office']['join_code']
    office_id = res.json['office']['id']

    # Create enrollment explicitly in DB since join endpoint may just validate or create too
    with client.application.app_context():
        enrollment = Enrollment(user_id=student_user_id, office_id=office_id)
        db.session.add(enrollment)
        db.session.commit()

    # Student joins office via join endpoint (should succeed or be idempotent)
    join_data = {"join_code": join_code}
    res = client.post('/office/join',
                      headers={'Authorization': f'Bearer {student_token}'},
                      json=join_data)
    assert res.status_code == 200

    # Start chat session using office_id saved earlier
    res = client.post('/chat/start',
                      headers={'Authorization': f'Bearer {student_token}'},
                      json={'office_id': office_id})
    assert res.status_code == 200
    session_id = res.json['session_id']

    # Mock AI response for chat message
    with patch('app.routes.chat.get_ai_response') as mock_ai:
        mock_ai.return_value = "Sure, how can I help?"
        res = client.post('/chat/message',
                          headers={'Authorization': f'Bearer {student_token}'},
                          json={'session_id': session_id, 'message': 'Hello!'})
        assert res.status_code == 200
        assert 'reply' in res.json
        assert res.json['reply'] == "Sure, how can I help?"
