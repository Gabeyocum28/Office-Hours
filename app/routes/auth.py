from flask import Blueprint, request, jsonify, current_app
from app import db
from app.models.db_models import User
from app.utils.auth_utils import hash_password, verify_password
from flask_jwt_extended import create_access_token

bp = Blueprint('auth', __name__, url_prefix='/auth')

@bp.route('/register', methods=['POST'])
def register():
    current_app.logger.info("Received registration request")
    try:
        data = request.json
        current_app.logger.info(f"Request data: {data}")
        
        name = data.get('name')
        email = data.get('email')
        password = data.get('password')
        role = data.get('role')  # 'teacher' or 'student'

        if not all([name, email, password, role]):
            current_app.logger.error("Missing required fields")
            return jsonify({'error': 'Missing required fields'}), 400

        if User.query.filter_by(email=email).first():
            current_app.logger.error(f"User already exists: {email}")
            return jsonify({'error': 'User already exists'}), 400

        user = User(
            name=name,
            email=email,
            password=hash_password(password),
            role=role
        )
        current_app.logger.info(f"Creating new user: {email}")
        db.session.add(user)
        db.session.commit()
        current_app.logger.info(f"User created successfully: {email}")
        return jsonify({'message': 'User registered successfully'}), 201
    except Exception as e:
        current_app.logger.error(f"Error in registration: {str(e)}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@bp.route('/login', methods=['POST'])
def login():
    data = request.json
    email = data.get('email')
    password = data.get('password')

    user = User.query.filter_by(email=email).first()
    if not user or not verify_password(password, user.password):
        return jsonify({'error': 'Invalid credentials'}), 401

    access_token = create_access_token(identity=str(user.id))
    return jsonify({
        'token': access_token,
        'user': {
            'id': user.id,
            'name': user.name,
            'role': user.role
        }
    }), 200
