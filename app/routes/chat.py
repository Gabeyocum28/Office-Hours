# app/routes/chat.py - FINAL FIXED VERSION

import os
import base64
from flask import Blueprint, request, jsonify, Response, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from app import db
from app.models.db_models import ChatSession, ChatMessage, Enrollment, Office
from datetime import datetime
from dotenv import load_dotenv
import threading
import logging

# Load .env variables first
load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import and initialize OpenAI with better compatibility
openai_client = None
try:
    import openai
    
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        logger.error("❌ OPENAI_API_KEY not found in environment variables")
    else:
        logger.info(f"✅ Found OpenAI API key: {api_key[:10]}...")
        
        # Try new OpenAI client first, fallback to older version
        try:
            # New OpenAI v1.0+ client
            from openai import OpenAI
            openai_client = OpenAI(api_key=api_key)
            logger.info("✅ Using new OpenAI client (v1.0+)")
        except (ImportError, TypeError) as e:
            # Fallback to older OpenAI client
            logger.info("Using legacy OpenAI client (v0.x)")
            openai.api_key = api_key
            openai_client = openai
        
        # Test the client
        try:
            if hasattr(openai_client, 'models'):
                # New client
                models = openai_client.models.list()
            else:
                # Old client
                models = openai_client.Model.list()
            logger.info("✅ OpenAI client initialized and tested successfully")
        except Exception as test_error:
            logger.error(f"❌ OpenAI client test failed: {test_error}")
            openai_client = None
            
except ImportError as import_error:
    logger.error(f"❌ OpenAI import error: {import_error}")
    openai_client = None
except Exception as init_error:
    logger.error(f"❌ OpenAI initialization error: {init_error}")
    openai_client = None

bp = Blueprint('chat', __name__, url_prefix='/chat')

def get_ai_response_with_vision(user_message, office_resources_text, conversation_history=None, image_data=None):
    """Enhanced AI response that can analyze video frames"""
    if not openai_client:
        return "OpenAI client not available. Please check your API key configuration."
    
    messages = []

    # Add context from office resources as system prompt if present
    if office_resources_text:
        system_prompt = f"""You are an AI teaching assistant. Use the following course context to answer questions:

{office_resources_text}

If you receive an image from the student's camera, describe what you can see and relate it to the course content when relevant. Be conversational and helpful."""
        messages.append({"role": "system", "content": system_prompt})

    # Add prior conversation history if available
    if conversation_history:
        messages.extend(conversation_history)

    # Prepare the user message
    if image_data:
        # OpenAI Vision API format
        user_content = [
            {"type": "text", "text": user_message},
            {
                "type": "image_url",
                "image_url": {
                    "url": image_data,
                    "detail": "low"  # Use "low" for faster processing
                }
            }
        ]
        messages.append({"role": "user", "content": user_content})
    else:
        messages.append({"role": "user", "content": user_message})

    try:
        # Use GPT-4o for vision (updated model)
        model = "gpt-4o" if image_data else "gpt-4o-mini"
        
        # Handle both new and old OpenAI client APIs
        if hasattr(openai_client, 'chat') and hasattr(openai_client.chat, 'completions'):
            # New OpenAI client (v1.0+)
            response = openai_client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=300,
                temperature=0.7
            )
            ai_message = response.choices[0].message.content.strip()
        else:
            # Old OpenAI client (v0.x)
            response = openai_client.ChatCompletion.create(
                model=model,
                messages=messages,
                max_tokens=300,
                temperature=0.7
            )
            ai_message = response.choices[0].message.content.strip()
        
        return ai_message

    except Exception as e:
        logger.error(f"OpenAI Vision API error: {e}")
        # Fallback to text-only response
        if "vision" in str(e).lower() or "gpt-4-vision" in str(e).lower():
            return get_ai_response(user_message + " (I can see your video feed)", office_resources_text, conversation_history)
        return "I'm having trouble processing that right now. Could you please try again?"

def get_ai_response(user_message, office_resources_text, conversation_history=None):
    """Regular AI response without vision (for text-only chat)"""
    if not openai_client:
        return "OpenAI client not available. Please check your API key configuration."
    
    messages = []

    # Add context from office resources as system prompt if present
    if office_resources_text:
        messages.append({"role": "system", "content": f"You are a helpful AI teaching assistant. Use the following context to answer questions:\n{office_resources_text}"})

    # Add prior conversation history if available
    if conversation_history:
        messages.extend(conversation_history)

    # Add current user message
    messages.append({"role": "user", "content": user_message})

    try:
        # Handle both new and old OpenAI client APIs
        if hasattr(openai_client, 'chat') and hasattr(openai_client.chat, 'completions'):
            # New OpenAI client (v1.0+)
            response = openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                max_tokens=250,
                temperature=0.7
            )
            ai_message = response.choices[0].message.content.strip()
        else:
            # Old OpenAI client (v0.x)
            response = openai_client.ChatCompletion.create(
                model="gpt-3.5-turbo",  # Use older model for compatibility
                messages=messages,
                max_tokens=250,
                temperature=0.7
            )
            ai_message = response.choices[0].message.content.strip()
        
        return ai_message

    except Exception as e:
        logger.error(f"OpenAI API error: {e}")
        return "I'm having trouble processing that right now. Could you please try again?"

def generate_avatar_video_async(message_id, ai_text):
    """Generate D-ID avatar video in background and store URL"""
    from app import create_app  # Import the app factory
    
    try:
        logger.info(f"Starting D-ID generation for message {message_id}")
        
        # Import here to avoid circular imports
        from app.utils.did_client import create_talking_avatar
        
        video_url = create_talking_avatar(ai_text)
        
        if video_url:
            logger.info(f"✅ D-ID video generated for message {message_id}: {video_url}")
            
            # FIXED: Create a new app context for the background thread
            app = create_app()
            with app.app_context():
                from app.models.db_models import ChatMessage
                message = ChatMessage.query.get(message_id)
                if message:
                    message.video_url = video_url
                    db.session.commit()
                    logger.info(f"💾 Stored video URL for message {message_id}")
                else:
                    logger.error(f"❌ Message {message_id} not found in database")
        else:
            logger.error(f"❌ D-ID video generation failed for message {message_id}")
            
    except Exception as e:
        logger.error(f"❌ D-ID background generation error: {e}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")

@bp.route('/start', methods=['POST'])
@jwt_required()
def start_chat():
    user_id = get_jwt_identity()
    data = request.get_json()
    office_id = data.get('office_id')

    logger.info(f"=== START CHAT ===")
    logger.info(f"user_id: {user_id}, office_id: {office_id}")

    if not office_id:
        return jsonify({"error": "Missing office_id"}), 400

    # Check if user is enrolled OR owns the office
    enrollment = Enrollment.query.filter_by(user_id=user_id, office_id=office_id).first()
    office = Office.query.get(office_id)
    
    if not enrollment and (not office or office.owner_id != int(user_id)):
        return jsonify({"error": "User not enrolled in this office"}), 403

    session = ChatSession.query.filter_by(user_id=user_id, office_id=office_id).first()
    if not session:
        session = ChatSession(user_id=user_id, office_id=office_id)
        db.session.add(session)
        db.session.commit()

    logger.info(f"✅ Chat session: {session.id}")
    return jsonify({"session_id": session.id})

@bp.route('/message', methods=['POST'])
@jwt_required()
def send_message():
    user_id = get_jwt_identity()
    data = request.get_json()
    session_id = data.get('session_id')
    user_message = data.get('message')
    use_avatar = data.get('use_avatar', False)
    video_frame = data.get('video_frame')

    logger.info(f"=== SEND MESSAGE ===")
    logger.info(f"user_id: {user_id}, session_id: {session_id}")
    logger.info(f"message: {user_message[:50]}...")
    logger.info(f"use_avatar: {use_avatar}, has_video: {bool(video_frame)}")

    if not session_id or not user_message:
        return jsonify({"error": "Missing session_id or message"}), 400

    session = ChatSession.query.get(session_id)
    if not session or session.user_id != int(user_id):
        return jsonify({"error": "Invalid chat session"}), 403

    # Verify office access
    office = Office.query.get(session.office_id)
    enrollment = Enrollment.query.filter_by(user_id=user_id, office_id=session.office_id).first()
    
    if not enrollment and (not office or office.owner_id != int(user_id)):
        return jsonify({"error": "Access denied to this office"}), 403

    # Save user's message
    user_msg = ChatMessage(session_id=session.id, sender='user', message=user_message)
    db.session.add(user_msg)
    db.session.commit()

    # Build conversation history (exclude current message)
    history_msgs = ChatMessage.query.filter_by(session_id=session_id).filter(
        ChatMessage.id != user_msg.id
    ).order_by(ChatMessage.timestamp.desc()).limit(10).all()
    
    conversation_history = [
        {"role": "assistant" if m.sender == "ai" else "user", "content": m.message}
        for m in reversed(history_msgs)  # Reverse to get chronological order
    ]

    # Get office resources for context
    resources = office.resources if office else []
    combined_text = " ".join([r.extracted_text or "" for r in resources])

    # Get AI reply
    if video_frame and video_frame.startswith('data:image'):
        logger.info("🎥 Using AI vision")
        ai_reply = get_ai_response_with_vision(
            user_message, 
            combined_text, 
            conversation_history=conversation_history,
            image_data=video_frame
        )
    else:
        logger.info("💬 Using text-only AI")
        ai_reply = get_ai_response(user_message, combined_text, conversation_history=conversation_history)

    # Save AI reply
    ai_msg = ChatMessage(session_id=session.id, sender='ai', message=ai_reply)
    db.session.add(ai_msg)
    db.session.commit()

    # Generate avatar video if requested
    avatar_generating = False
    if use_avatar and os.getenv("DID_API_KEY"):
        try:
            thread = threading.Thread(target=generate_avatar_video_async, args=(ai_msg.id, ai_reply))
            thread.daemon = True
            thread.start()
            avatar_generating = True
            logger.info("🎬 Started D-ID avatar generation")
        except Exception as e:
            logger.error(f"❌ Failed to start D-ID generation: {e}")

    return jsonify({
        "reply": ai_reply,
        "message_id": ai_msg.id,
        "avatar_generating": avatar_generating,
        "has_vision": bool(video_frame)
    })

@bp.route('/tts', methods=['POST'])
@jwt_required()
def text_to_speech():
    """Convert text to speech using OpenAI's TTS API"""
    data = request.get_json()
    text = data.get('text', '')
    voice = data.get('voice', 'alloy')
    
    logger.info(f"🔊 TTS Request: {text[:50]}...")
    logger.info(f"OpenAI client available: {openai_client is not None}")
    
    if not openai_client:
        logger.error("❌ OpenAI client not available for TTS")
        return jsonify({"error": "OpenAI client not available. Please check your API key configuration."}), 500
    
    if not text:
        return jsonify({"error": "No text provided"}), 400
    
    # Limit text length for TTS
    if len(text) > 4096:
        text = text[:4096] + "..."
    
    try:
        logger.info(f"🔊 Generating TTS for: {text[:50]}...")
        
        # Handle both new and old OpenAI client APIs
        if hasattr(openai_client, 'audio') and hasattr(openai_client.audio, 'speech'):
            # New OpenAI client (v1.0+)
            response = openai_client.audio.speech.create(
                model="tts-1",  # Fast model
                voice=voice,    # alloy, echo, fable, onyx, nova, shimmer
                input=text
            )
            
            # FIXED: Proper response streaming
            def generate():
                for chunk in response.iter_bytes(chunk_size=1024):
                    yield chunk
            
            logger.info(f"✅ TTS generated successfully")
            
            return Response(
                generate(),
                mimetype="audio/mpeg",
                headers={
                    "Content-Disposition": "inline; filename=speech.mp3",
                    "Cache-Control": "no-cache"
                }
            )
        else:
            # Old OpenAI client doesn't have TTS - fallback
            logger.error("❌ TTS not available in older OpenAI client")
            return jsonify({"error": "TTS requires OpenAI v1.0+. Please upgrade: pip install openai>=1.0"}), 500
        
    except Exception as e:
        logger.error(f"❌ OpenAI TTS error: {e}")
        logger.error(f"Error type: {type(e)}")
        return jsonify({"error": f"TTS generation failed: {str(e)}"}), 500

@bp.route('/message/<int:message_id>/avatar', methods=['GET'])
@jwt_required()
def get_avatar_video(message_id):
    """Check if avatar video is ready for a message"""
    user_id = get_jwt_identity()
    
    message = ChatMessage.query.get(message_id)
    if not message:
        return jsonify({"error": "Message not found"}), 404
    
    session = ChatSession.query.get(message.session_id)
    if not session or session.user_id != int(user_id):
        return jsonify({"error": "Access denied"}), 403
    
    # RETURN ACTUAL VIDEO STATUS
    if hasattr(message, 'video_url') and message.video_url:
        return jsonify({
            "video_ready": True,
            "video_url": message.video_url,
            "status": "done"
        })
    else:
        return jsonify({
            "video_ready": False,
            "video_url": None,
            "status": "generating"
        })

@bp.route('/history/<int:session_id>', methods=['GET'])
@jwt_required()
def get_history(session_id):
    user_id = get_jwt_identity()
    logger.info(f"Getting history for session {session_id}, user {user_id}")

    session = ChatSession.query.get(session_id)
    if not session:
        logger.error(f"No session found for ID {session_id}")
        return jsonify({"error": "Session not found"}), 404
        
    if int(session.user_id) != int(user_id):
        logger.error(f"User mismatch: session.user_id={session.user_id}, token.user_id={user_id}")
        return jsonify({"error": "Access denied"}), 403

    messages = ChatMessage.query.filter_by(session_id=session_id).order_by(ChatMessage.timestamp).all()
    history = []
    for m in messages:
        msg_data = {
            "sender": m.sender, 
            "message": m.message, 
            "timestamp": m.timestamp.isoformat(),
            "message_id": m.id
        }
        # ADD VIDEO URL IF EXISTS
        if hasattr(m, 'video_url') and m.video_url:
            msg_data["video_url"] = m.video_url
        history.append(msg_data)

    return jsonify({"history": history})