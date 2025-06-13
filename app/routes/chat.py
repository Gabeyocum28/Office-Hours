import os
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app import db
from app.models.db_models import ChatSession, ChatMessage, Enrollment, Office
from datetime import datetime
import openai
from dotenv import load_dotenv

# Load .env variables
load_dotenv()

openai.api_key = os.getenv("OPENAI_API_KEY")

bp = Blueprint('chat', __name__, url_prefix='/chat')

def get_ai_response(user_message, office_resources_text, conversation_history=None):
    # Build messages payload for OpenAI chat
    messages = []

    # Add context from office resources as system prompt if present
    if office_resources_text:
        messages.append({"role": "system", "content": f"Use the following context to answer questions:\n{office_resources_text}"})

    # Add prior conversation history if available
    if conversation_history:
        messages.extend(conversation_history)

    # Add current user message
    messages.append({"role": "user", "content": user_message})

    try:
        response = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=messages,
            max_tokens=200,
            temperature=0.7,
            n=1
        )
        ai_message = response.choices[0].message['content'].strip()
        return ai_message

    except Exception as e:
        print(f"OpenAI API error: {e}")
        return "Sorry, I couldn't process that right now."

@bp.route('/start', methods=['POST'])
@jwt_required()
def start_chat():
    user_id = get_jwt_identity()
    data = request.get_json()
    office_id = data.get('office_id')

    if not office_id:
        return jsonify({"error": "Missing office_id"}), 400

    enrollment = Enrollment.query.filter_by(user_id=user_id, office_id=office_id).first()
    if not enrollment:
        return jsonify({"error": "User not enrolled in this office"}), 403

    session = ChatSession.query.filter_by(user_id=user_id, office_id=office_id).first()
    if not session:
        session = ChatSession(user_id=user_id, office_id=office_id)
        db.session.add(session)
        db.session.commit()

    return jsonify({"session_id": session.id})


@bp.route('/message', methods=['POST'])
@jwt_required()
def send_message():
    user_id = get_jwt_identity()
    data = request.get_json()
    session_id = data.get('session_id')
    user_message = data.get('message')

    print(f"user_id from JWT: {user_id}")
    print(f"session_id from request: {session_id}")

    if not session_id or not user_message:
        print("Missing session_id or message in request")
        return jsonify({"error": "Missing session_id or message"}), 400

    session = ChatSession.query.get(session_id)
    print(f"session from DB: {session}")

    if not session:
        print("No session found for that id.")
        return jsonify({"error": "Invalid chat session"}), 403

    # Cast user IDs to int for safe comparison
    try:
        session_user_id = int(session.user_id)
        token_user_id = int(user_id)
    except Exception as e:
        print(f"Error casting user ids to int: {e}")
        return jsonify({"error": "Invalid user identity"}), 403

    print(f"session_user_id: {session_user_id}, token_user_id: {token_user_id}")

    if session_user_id != token_user_id:
        print("Session user_id does not match JWT user_id after int casting.")
        return jsonify({"error": "Invalid chat session"}), 403

    # Save user's message
    user_msg = ChatMessage(session_id=session.id, sender='user', message=user_message)
    db.session.add(user_msg)
    db.session.commit()

    # Build conversation history for AI context
    history_msgs = ChatMessage.query.filter_by(session_id=session_id).order_by(ChatMessage.timestamp).all()
    conversation_history = [
        {"role": "assistant" if m.sender == "ai" else "user", "content": m.message}
        for m in history_msgs
    ]

    # Get office resources text to provide context
    office = Office.query.get(session.office_id)
    resources = office.resources if office else []
    combined_text = " ".join([r.extracted_text or "" for r in resources])

    # Get AI reply
    ai_reply = get_ai_response(user_message, combined_text, conversation_history=conversation_history)

    # Save AI reply
    ai_msg = ChatMessage(session_id=session.id, sender='ai', message=ai_reply)
    db.session.add(ai_msg)
    db.session.commit()

    return jsonify({"reply": ai_reply})




@bp.route('/history/<int:session_id>', methods=['GET'])
@jwt_required()
def get_history(session_id):
    user_id = get_jwt_identity()

    session = ChatSession.query.get(session_id)
    if not session or session.user_id != user_id:
        return jsonify({"error": "Invalid chat session"}), 403

    messages = ChatMessage.query.filter_by(session_id=session_id).order_by(ChatMessage.timestamp).all()
    history = [{"sender": m.sender, "message": m.message, "timestamp": m.timestamp.isoformat()} for m in messages]

    return jsonify({"history": history})
