from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from werkzeug.utils import secure_filename
import os
import uuid
from app import db
from app.models.db_models import User, Office, Resource
from app.utils.file_processor import extract_text_from_file

bp = Blueprint('upload', __name__, url_prefix='/upload')

ALLOWED_EXTENSIONS = {
    'txt', 'pdf', 'doc', 'docx', 'ppt', 'pptx', 
    'jpg', 'jpeg', 'png', 'gif', 'mp4', 'mov', 'avi'
}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_file_type(filename):
    """Categorize file type for processing"""
    ext = filename.rsplit('.', 1)[1].lower()
    if ext in ['txt']:
        return 'text'
    elif ext in ['pdf']:
        return 'pdf'
    elif ext in ['doc', 'docx']:
        return 'document'
    elif ext in ['ppt', 'pptx']:
        return 'presentation'
    elif ext in ['jpg', 'jpeg', 'png', 'gif']:
        return 'image'
    elif ext in ['mp4', 'mov', 'avi']:
        return 'video'
    return 'unknown'

@bp.route('/file', methods=['POST'])
@jwt_required()
def upload_file():
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        
        # Check if user is a teacher
        if user.role != 'teacher':
            return jsonify({'error': 'Only teachers can upload files'}), 403
        
        office_id = request.form.get('office_id')
        if not office_id:
            return jsonify({'error': 'Office ID is required'}), 400
        
        # Verify teacher owns the office
        office = Office.query.get(office_id)
        if not office or office.owner_id != int(user_id):
            return jsonify({'error': 'You can only upload to your own offices'}), 403
        
        # Check if file is present
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        if not allowed_file(file.filename):
            return jsonify({'error': 'File type not allowed'}), 400
        
        # Generate unique filename
        original_filename = secure_filename(file.filename)
        file_extension = original_filename.rsplit('.', 1)[1].lower()
        unique_filename = f"{uuid.uuid4().hex}.{file_extension}"
        
        # Ensure upload directory exists
        upload_dir = current_app.config['UPLOAD_FOLDER']
        office_upload_dir = os.path.join(upload_dir, f"office_{office_id}")
        os.makedirs(office_upload_dir, exist_ok=True)
        
        # Save file
        file_path = os.path.join(office_upload_dir, unique_filename)
        file.save(file_path)
        
        # Get file size
        file_size = os.path.getsize(file_path)
        file_type = get_file_type(original_filename)
        
        # Create resource record
        resource = Resource(
            office_id=office_id,
            file_path=file_path,
            file_name=original_filename,
            file_type=file_type,
            file_size=file_size,
            processed=False
        )
        
        db.session.add(resource)
        db.session.commit()
        
        # Extract text in background (for now, do it immediately)
        try:
            extracted_text = extract_text_from_file(file_path, file_type)
            if extracted_text:
                resource.extracted_text = extracted_text
                resource.processed = True
                db.session.commit()
        except Exception as e:
            current_app.logger.error(f"Text extraction failed for {file_path}: {e}")
            # File is saved but text extraction failed - that's ok
        
        return jsonify({
            'message': 'File uploaded successfully',
            'resource': {
                'id': resource.id,
                'filename': original_filename,
                'file_type': file_type,
                'file_size': file_size,
                'processed': resource.processed
            }
        }), 201
        
    except Exception as e:
        current_app.logger.error(f"Upload error: {e}")
        db.session.rollback()
        return jsonify({'error': 'Upload failed'}), 500

@bp.route('/office/<int:office_id>/files', methods=['GET'])
@jwt_required()
def get_office_files(office_id):
    """Get all files for an office"""
    user_id = get_jwt_identity()
    
    # Check if user has access to this office (owner or enrolled)
    office = Office.query.get(office_id)
    if not office:
        return jsonify({'error': 'Office not found'}), 404
    
    # Check access
    from app.models.db_models import Enrollment
    has_access = (
        office.owner_id == int(user_id) or
        Enrollment.query.filter_by(user_id=user_id, office_id=office_id).first()
    )
    
    if not has_access:
        return jsonify({'error': 'Access denied'}), 403
    
    resources = Resource.query.filter_by(office_id=office_id).all()
    
    files_data = []
    for resource in resources:
        files_data.append({
            'id': resource.id,
            'filename': resource.file_name,
            'file_type': resource.file_type,
            'file_size': resource.file_size,
            'processed': resource.processed,
            'uploaded_at': resource.uploaded_at.isoformat()
        })
    
    return jsonify({'files': files_data}), 200

@bp.route('/file/<int:resource_id>', methods=['DELETE'])
@jwt_required()
def delete_file(resource_id):
    """Delete a file (teacher only)"""
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    
    if user.role != 'teacher':
        return jsonify({'error': 'Only teachers can delete files'}), 403
    
    resource = Resource.query.get(resource_id)
    if not resource:
        return jsonify({'error': 'File not found'}), 404
    
    # Check if teacher owns the office
    office = Office.query.get(resource.office_id)
    if office.owner_id != int(user_id):
        return jsonify({'error': 'You can only delete files from your own offices'}), 403
    
    # Delete physical file
    try:
        if os.path.exists(resource.file_path):
            os.remove(resource.file_path)
    except Exception as e:
        current_app.logger.error(f"Failed to delete file {resource.file_path}: {e}")
    
    # Delete database record
    db.session.delete(resource)
    db.session.commit()
    
    return jsonify({'message': 'File deleted successfully'}), 200