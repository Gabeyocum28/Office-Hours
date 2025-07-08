import jwt
import datetime
import secrets
import string
from werkzeug.security import generate_password_hash, check_password_hash
from flask import current_app

def hash_password(password):
    return generate_password_hash(password)

def verify_password(password, hashed):
    return check_password_hash(hashed, password)

def generate_token(user_id):
    payload = {
        'user_id': user_id,
        'exp': datetime.datetime.utcnow() + datetime.timedelta(days=1)
    }
    return jwt.encode(payload, current_app.config['SECRET_KEY'], algorithm='HS256')

def decode_token(token):
    try:
        payload = jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=['HS256'])
        return payload['user_id']
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None

def generate_verification_token(length=32):
    """Generate a secure random token for email verification"""
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))

def generate_token_expiry(hours=24):
    """Generate token expiry time (default 24 hours from now)"""
    return datetime.datetime.utcnow() + datetime.timedelta(hours=hours)

def is_token_expired(expiry_time):
    """Check if a token has expired"""
    if not expiry_time:
        return True
    return datetime.datetime.utcnow() > expiry_time