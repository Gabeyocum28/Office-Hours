# routes/office.py

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app import db
from app.models.db_models import User, Office, Enrollment
import string
import random

bp = Blueprint("office", __name__, url_prefix="/office")

def generate_join_code(length=6):
    """Generate a random uppercase alphanumeric join code."""
    characters = string.ascii_uppercase + string.digits
    return ''.join(random.choices(characters, k=length))

@bp.route("/create", methods=["POST"])
@jwt_required()
def create_office():
    print("create_office route hit")
    user_id = get_jwt_identity()
    user = User.query.get(user_id)

    if user.role != "teacher":
        return jsonify({"error": "Only teachers can create offices."}), 403

    data = request.get_json()
    name = data.get("name")

    if not name:
        return jsonify({"error": "Office name is required."}), 400

    # Generate unique join code (retry if collision)
    while True:
        join_code = generate_join_code()
        if not Office.query.filter_by(join_code=join_code).first():
            break

    new_office = Office(name=name, owner_id=user_id, join_code=join_code)
    db.session.add(new_office)
    db.session.commit()

    return jsonify({
        "message": "Office created successfully",
        "office": {
            "id": new_office.id,
            "name": new_office.name,
            "join_code": new_office.join_code
        }
    }), 201

@bp.route("/join", methods=["POST"])
@jwt_required()
def join_office():
    user_id = get_jwt_identity()
    data = request.get_json()
    join_code = data.get("join_code")

    if not join_code:
        return jsonify({"error": "Join code is required."}), 400

    office = Office.query.filter_by(join_code=join_code).first()
    if not office:
        return jsonify({"error": "Office not found."}), 404

    # Check if already enrolled
    existing_enrollment = Enrollment.query.filter_by(user_id=user_id, office_id=office.id).first()
    if existing_enrollment:
        return jsonify({"message": "Already joined this office."}), 200

    # Add enrollment
    enrollment = Enrollment(user_id=user_id, office_id=office.id)
    db.session.add(enrollment)
    db.session.commit()

    return jsonify({"message": f"Joined office '{office.name}' successfully."}), 201

@bp.route("/edit/<int:office_id>", methods=["PUT"])
@jwt_required()
def edit_office(office_id):
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    office = Office.query.get(office_id)

    if not office:
        return jsonify({"error": "Office not found."}), 404

    if office.owner_id != user_id:
        return jsonify({"error": "Only the owner can edit this office."}), 403

    data = request.get_json()
    name = data.get("name")

    if name:
        office.name = name

    db.session.commit()

    return jsonify({
        "message": "Office updated successfully.",
        "office": {
            "id": office.id,
            "name": office.name,
            "join_code": office.join_code
        }
    }), 200

print("office.py loaded, blueprint name:", bp.name)

