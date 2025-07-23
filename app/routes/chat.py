# app/routes/chat.py - STREAMING & OPTIMIZED VERSION

import os
import base64
import time
import hashlib
import json
import threading
import logging
import queue
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional, Dict, Any, List, Generator

from flask import Blueprint, request, jsonify, Response, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from app import db
from app.models.db_models import ChatSession, ChatMessage, Enrollment, Office
from dotenv import load_dotenv

# Import OpenAI and httpx for API calls
import openai
import httpx

# PIL for image optimization
try:
    from PIL import Image
    import io
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    print("⚠️ PIL not available - image optimization disabled")

# Redis for caching with optimized connection pool
try:
    import redis
    redis_client = redis.Redis(
        host='localhost', 
        port=6379, 
        db=0, 
        decode_responses=True, 
        socket_timeout=2,
        socket_connect_timeout=1
    )
    redis_client.ping()
    print("✅ Redis connected with optimized pool - caching enabled")
except Exception as e:
    redis_client = None
    print(f"⚠️ Redis not available ({e}) - caching disabled")

# Load .env variables
load_dotenv()

# Setup enhanced logging with performance tracking
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - [%(funcName)s:%(lineno)d] - %(message)s'
)
logger = logging.getLogger(__name__)

# Performance metrics tracking
performance_metrics = {
    'llm_response_times': [],
    'tts_generation_times': [],
    'total_request_times': [],
    'cache_hit_rates': {'tts_hits': 0, 'tts_total': 0},
    'concurrent_requests': 0,
    'error_counts': {'llm_errors': 0, 'tts_errors': 0, 'network_errors': 0}
}

def log_performance_metric(metric_type, value, details=None):
    """Log performance metrics for monitoring"""
    current_time = time.time()
    performance_metrics[metric_type].append({
        'timestamp': current_time,
        'value': value,
        'details': details or {}
    })
    
    # Keep only last 100 entries per metric to prevent memory growth
    if len(performance_metrics[metric_type]) > 100:
        performance_metrics[metric_type] = performance_metrics[metric_type][-100:]
    
    logger.info(f"PERF_{metric_type.upper()}: {value:.3f}s - {details}")

# --- Model & Performance Configuration ---
# Ultra-fast models for near real-time performance
FAST_MODEL = "gpt-4o-mini"  # Fastest text model
VISION_MODEL = "gpt-4o-mini"  # Use mini for vision too for speed
TTS_MODEL = "tts-1"  # Fastest TTS model
TTS_VOICE = "onyx"  # Optimized voice

# Reduced token limits for faster responses
MAX_TOKENS = 300  # Reduced further for ultra-fast responses
MAX_VISION_TOKENS = 200  # Even smaller for vision queries 

# Initialize OpenAI client with performance optimizations
openai_client = None
try:
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if openai_api_key:
        # Initialize with optimized HTTP client for performance
        openai_client = openai.OpenAI(
            api_key=openai_api_key,
            timeout=httpx.Timeout(30.0, connect=5.0),  # Faster timeouts
            max_retries=1,  # Reduce retries for speed
            http_client=httpx.Client(
                limits=httpx.Limits(
                    max_connections=100,  # Connection pooling
                    max_keepalive_connections=20,
                    keepalive_expiry=30.0
                ),
                timeout=httpx.Timeout(30.0, connect=5.0),
                http2=True  # Enable HTTP/2 for better performance
            )
        )
        logger.info("✅ OpenAI client initialized with performance optimizations.")
    else:
        logger.warning("⚠️ OPENAI_API_KEY not found in environment variables. OpenAI features will be disabled.")
except Exception as e:
    logger.error(f"❌ Error initializing OpenAI client: {e}")
    openai_client = None

bp = Blueprint('chat', __name__, url_prefix='/chat')

@bp.route('/start_session', methods=['POST'])
@jwt_required()
def start_session():
    user_id = get_jwt_identity()
    office_id = request.json.get('office_id')
    if not office_id:
        return jsonify({"error": "Office ID is required"}), 400

    enrollment = Enrollment.query.filter_by(user_id=user_id, office_id=office_id).first()
    office = Office.query.get(office_id)
    if not enrollment and (not office or office.owner_id != int(user_id)):
        return jsonify({"error": "User not enrolled in this office"}), 403
    session = ChatSession.query.filter_by(user_id=user_id, office_id=office_id).first()
    if not session:
        session = ChatSession(user_id=user_id, office_id=office_id)
        db.session.add(session)
        db.session.commit()
    return jsonify({"session_id": session.id})

@bp.route('/history/<int:session_id>', methods=['GET'])
@jwt_required()
def get_history(session_id):
    user_id = get_jwt_identity()
    session = ChatSession.query.get(session_id)
    if not session or int(session.user_id) != int(user_id):
        return jsonify({"error": "Access denied"}), 403
    messages = ChatMessage.query.filter_by(session_id=session_id).order_by(ChatMessage.timestamp).all()
    history = [{"sender": m.sender, "message": m.message, "timestamp": m.timestamp.isoformat(), "message_id": m.id} for m in messages]
    return jsonify({"history": history})

@bp.route('/health', methods=['GET'])
def health_check():
    return jsonify({
        "status": "streaming_ready",
        "optimizations": {
            "openai_available": openai_client is not None,
            "pil_available": PIL_AVAILABLE,
            "redis_available": redis_client is not None
        }
    })

@bp.route('/metrics', methods=['GET'])
def get_performance_metrics():
    """Get detailed performance metrics for monitoring"""
    try:
        # Calculate cache hit rate
        cache_stats = performance_metrics['cache_hit_rates']
        cache_hit_rate = (cache_stats['tts_hits'] / cache_stats['tts_total'] * 100) if cache_stats['tts_total'] > 0 else 0
        
        # Calculate average response times
        recent_requests = performance_metrics['total_request_times'][-20:]  # Last 20 requests
        avg_response_time = sum(req['value'] for req in recent_requests) / len(recent_requests) if recent_requests else 0
        
        # Get recent error rates
        total_errors = sum(performance_metrics['error_counts'].values())
        
        metrics = {
            "timestamp": time.time(),
            "performance": {
                "avg_response_time_ms": round(avg_response_time * 1000, 2),
                "cache_hit_rate_percent": round(cache_hit_rate, 2),
                "concurrent_requests": performance_metrics['concurrent_requests'],
                "total_errors": total_errors,
                "error_breakdown": performance_metrics['error_counts']
            },
            "recent_metrics": {
                "last_20_requests": [
                    {
                        "response_time_ms": round(req['value'] * 1000, 2),
                        "details": req.get('details', {})
                    } for req in recent_requests
                ],
                "cache_stats": cache_stats
            },
            "system_status": {
                "openai_available": openai_client is not None,
                "redis_available": redis_client is not None,
                "pil_available": PIL_AVAILABLE
            }
        }
        
        return jsonify(metrics)
        
    except Exception as e:
        logger.error(f"Error generating metrics: {e}")
        return jsonify({"error": "Failed to generate metrics", "details": str(e)}), 500

# Helper function to get chat history for LLM context with caching
def get_chat_history_for_llm(app, session_id: int) -> List[Dict[str, Any]]:
    # Try to get chat history from cache first
    cache_key = f"chat_history:{session_id}"
    
    if redis_client:
        try:
            cached_history = redis_client.get(cache_key)
            if cached_history:
                import json
                return json.loads(cached_history)
        except Exception as e:
            logger.warning(f"Failed to read chat history from cache: {e}")
    
    # Fetch from database if not in cache
    messages = ChatMessage.query.filter_by(session_id=session_id).order_by(ChatMessage.timestamp).all()
    history = []
    for msg in messages:
        role = 'user' if msg.sender == 'user' else 'assistant'
        history.append({"role": role, "content": msg.message})
    
    # Cache the history for faster subsequent requests
    if redis_client and history:
        try:
            import json
            redis_client.setex(cache_key, 300, json.dumps(history))  # Cache for 5 minutes
        except Exception as e:
            logger.warning(f"Failed to cache chat history: {e}")
    
    return history

# Function to optimize image size (optional, for vision model)
def optimize_image(image_data: str) -> str:
    if not PIL_AVAILABLE:
        logger.warning("PIL not available, skipping image optimization.")
        return image_data

    try:
        header, encoded = image_data.split(",", 1)
        data = base64.b64decode(encoded)
        img = Image.open(io.BytesIO(data))

        # Resize if image is too large (e.g., max 1024 on longest side)
        max_size = 1024
        if max(img.size) > max_size:
            img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)

        # Compress to JPEG
        output_buffer = io.BytesIO()
        img.save(output_buffer, format="JPEG", quality=70) # Adjust quality as needed
        optimized_data = output_buffer.getvalue()
        
        logger.info(f"📸 Image optimized: {len(data)} -> {len(optimized_data)} bytes")
        return header.split(';')[0] + ";base64," + base64.b64encode(optimized_data).decode('utf-8')
    except Exception as e:
        logger.error(f"❌ Error optimizing image: {e}")
        return image_data # Return original if optimization fails

# Actual LLM/TTS integration with OpenAI
def get_llm_and_tts_stream_from_openai(app, user_message: str, video_frame: Optional[str], session_id: int) -> Generator[Dict[str, Any], None, None]:
    if not openai_client:
        yield {'type': 'error', 'content': "OpenAI client not initialized. Please set OPENAI_API_KEY."}
        return

    start_time = time.time()
    performance_metrics['concurrent_requests'] += 1
    full_text_response = ""
    text_buffer = ""
    sentence_endings = '.!?'
    min_sentence_length = 20  # Minimum characters for a sentence
    sentence_complete_words = 4  # Minimum words for a complete sentence
    accumulated_words = []
    
    # Performance tracking variables
    llm_start_time = time.time()
    first_token_time = None
    tts_generation_times = []
    total_chunks_generated = 0
    
    try:
        # No 'with app.app_context()' here, as it's expected to be called within one already
        # Prepare chat history for LLM context (with caching)
        chat_history = get_chat_history_for_llm(app, session_id)
        
        # Check if we have a cached response for similar recent queries
        query_cache_key = f"llm_response:{hashlib.md5((user_message + str(len(chat_history))).encode()).hexdigest()[:16]}"
        if redis_client and not video_frame:  # Only cache text-only responses
            try:
                cached_response = redis_client.get(query_cache_key)
                if cached_response:
                    logger.info(f"🚀 LLM cache hit for query: '{user_message[:30]}...'")
                    import json
                    cached_data = json.loads(cached_response)
                    # Stream the cached response
                    for chunk in cached_data['text_chunks']:
                        yield {'type': 'text', 'content': chunk}
                    for audio_chunk in cached_data['audio_chunks']:
                        yield {'type': 'audio', 'content': audio_chunk}
                    yield {'type': 'end', 'processing_time': 0.1, 'cached': True}
                    return
            except Exception as e:
                logger.warning(f"LLM cache read failed: {e}")
        
        # Add current user message to history
        current_message_content = []
        current_message_content.append({"type": "text", "text": user_message})

        if video_frame:
            # Optimize image before sending to OpenAI
            optimized_video_frame = optimize_image(video_frame)
            current_message_content.append({"type": "image_url", "image_url": {"url": optimized_video_frame}})
            model_to_use = VISION_MODEL # Use vision model if image is present
        else:
            model_to_use = FAST_MODEL # Use fast model for text-only

        # Append current user message to chat history for the API call
        chat_history.append({"role": "user", "content": current_message_content})

        # Use vision-specific token limit if image present
        token_limit = MAX_VISION_TOKENS if video_frame else MAX_TOKENS
        
        logger.info(f"Sending request to OpenAI LLM ({model_to_use}, max_tokens={token_limit})...")
        llm_response_stream = openai_client.chat.completions.create(
            model=model_to_use,
            messages=chat_history,
            max_tokens=token_limit,
            stream=True,  # Enable streaming
            temperature=0.5,  # Lower for faster, more focused responses
            top_p=0.85,  # More focused for speed
            frequency_penalty=0.1,  # Reduce repetition
            presence_penalty=0.1
        )

        def generate_tts_for_chunk(text_chunk: str) -> Optional[str]:
            """Generate TTS for a chunk of text and return base64 audio"""
            if not text_chunk.strip():
                return None
            
            nonlocal total_chunks_generated
            total_chunks_generated += 1
            tts_start_time = time.time()
            
            # Check cache first with performance optimization
            tts_cache_key = f"tts:{hashlib.md5(text_chunk.encode('utf-8')).hexdigest()[:16]}"
            performance_metrics['cache_hit_rates']['tts_total'] += 1
            
            if redis_client:
                try:
                    cached_audio = redis_client.get(tts_cache_key)
                    if cached_audio:
                        performance_metrics['cache_hit_rates']['tts_hits'] += 1
                        cache_time = time.time() - tts_start_time
                        tts_generation_times.append(cache_time)
                        logger.info(f"🔊 TTS cache hit ({cache_time*1000:.1f}ms): '{text_chunk[:30]}...'")
                        return cached_audio
                except Exception as e:
                    logger.warning(f"Redis cache read failed: {e}")
                    performance_metrics['error_counts']['network_errors'] += 1

            try:
                logger.info(f"🔊 Generating TTS for chunk: '{text_chunk[:30]}...'")
                tts_response = openai_client.audio.speech.create(
                    model=TTS_MODEL,
                    voice=TTS_VOICE,
                    input=text_chunk,
                    response_format="mp3"
                )
                
                # Read audio data
                audio_data_buffer = io.BytesIO()
                for audio_chunk in tts_response.iter_bytes(chunk_size=4096):
                    audio_data_buffer.write(audio_chunk)
                    
                full_audio_bytes = audio_data_buffer.getvalue()
                base64_audio = base64.b64encode(full_audio_bytes).decode('utf-8')

                # Cache the result with pipeline for better performance
                if redis_client:
                    try:
                        # Use pipeline for better performance
                        pipe = redis_client.pipeline()
                        pipe.set(tts_cache_key, base64_audio, ex=7200)  # Cache for 2 hours
                        pipe.execute()
                    except Exception as e:
                        logger.warning(f"Redis cache write failed: {e}")
                    
                tts_time = time.time() - tts_start_time
                tts_generation_times.append(tts_time)
                logger.info(f"✅ TTS chunk generated ({len(full_audio_bytes)} bytes, {tts_time:.3f}s)")
                return base64_audio
                
            except Exception as e:
                performance_metrics['error_counts']['tts_errors'] += 1
                tts_time = time.time() - tts_start_time
                logger.error(f"❌ TTS generation failed for chunk ({tts_time:.3f}s): {e}")
                return None

        # Stream LLM response and generate TTS for complete sentences
        for chunk in llm_response_stream:
            if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                content_chunk = chunk.choices[0].delta.content
                full_text_response += content_chunk
                text_buffer += content_chunk
                
                # Track first token time
                if first_token_time is None:
                    first_token_time = time.time()
                    first_token_latency = first_token_time - llm_start_time
                    logger.info(f"⚡ First token received in {first_token_latency:.3f}s")
                
                # Yield the text chunk immediately
                yield {'type': 'text', 'content': content_chunk}
                
                # SIMPLIFIED: Only generate TTS for complete sentences to prevent overlaps
                sentence_end_pos = -1
                for ending in sentence_endings:
                    pos = text_buffer.find(ending)
                    if pos != -1:
                        sentence_end_pos = max(sentence_end_pos, pos)
                
                if sentence_end_pos != -1:
                    # Found a complete sentence
                    sentence = text_buffer[:sentence_end_pos + 1].strip()
                    text_buffer = text_buffer[sentence_end_pos + 1:]
                    
                    # Only generate TTS for substantial, complete sentences
                    word_count = len(sentence.split())
                    if len(sentence) >= min_sentence_length and word_count >= sentence_complete_words:
                        logger.info(f"🎵 Generating TTS for complete sentence: '{sentence}'")
                        audio_data = generate_tts_for_chunk(sentence)
                        if audio_data:
                            yield {'type': 'audio', 'content': audio_data}
                    else:
                        logger.info(f"🎵 Skipping short sentence: '{sentence}' (too short for clean TTS)")
                
        llm_total_time = time.time() - llm_start_time
        logger.info(f"LLM streaming complete. Response: {len(full_text_response)} chars, {llm_total_time:.3f}s total")
        
        # Log detailed performance metrics
        if tts_generation_times:
            avg_tts_time = sum(tts_generation_times) / len(tts_generation_times)
            max_tts_time = max(tts_generation_times)
            logger.info(f"TTS Performance: avg={avg_tts_time:.3f}s, max={max_tts_time:.3f}s, chunks={len(tts_generation_times)}")

        # Generate TTS for any remaining complete sentences in buffer
        if text_buffer.strip():
            final_text = text_buffer.strip()
            # Only generate TTS for substantial remaining text that could be a sentence
            word_count = len(final_text.split())
            if len(final_text) >= min_sentence_length and word_count >= sentence_complete_words:
                logger.info(f"🎵 Generating final TTS for remaining text: '{final_text}'")
                audio_data = generate_tts_for_chunk(final_text)
                if audio_data:
                    yield {'type': 'audio', 'content': audio_data}
            else:
                logger.info(f"🎵 Skipping final text (too short): '{final_text}'")
        
        # Cache the complete response for future similar queries (text-only)
        if redis_client and not video_frame and full_text_response:
            try:
                import json
                cache_data = {
                    'text_chunks': [full_text_response],  # Store complete response
                    'audio_chunks': [],  # Audio will be regenerated for freshness
                    'timestamp': time.time()
                }
                redis_client.setex(query_cache_key, 1800, json.dumps(cache_data))  # Cache for 30 minutes
                logger.info(f"💾 Cached LLM response for future use")
            except Exception as e:
                logger.warning(f"Failed to cache LLM response: {e}")

    except openai.APIError as e:
        performance_metrics['error_counts']['llm_errors'] += 1
        logger.error(f"❌ OpenAI API Error: {e}")
        yield {'type': 'error', 'content': f"OpenAI API Error: {e.status_code} - {e.response}"}
    except httpx.RequestError as e:
        performance_metrics['error_counts']['network_errors'] += 1
        logger.error(f"❌ Network Error during OpenAI API call: {e}")
        yield {'type': 'error', 'content': f"Network Error: Could not connect to OpenAI API. {e}"}
    except Exception as e:
        performance_metrics['error_counts']['llm_errors'] += 1
        logger.error(f"❌ An unexpected error occurred during LLM/TTS streaming: {e}", exc_info=True)
        yield {'type': 'error', 'content': f"An internal server error occurred: {e}"}
    finally:
        # Performance metrics and cleanup
        performance_metrics['concurrent_requests'] -= 1
        processing_time = time.time() - start_time
        
        # Log comprehensive performance data
        log_performance_metric('total_request_times', processing_time, {
            'response_length': len(full_text_response),
            'tts_chunks': total_chunks_generated,
            'first_token_latency': first_token_time - llm_start_time if first_token_time else None,
            'llm_total_time': llm_total_time if 'llm_total_time' in locals() else None
        })
        
        yield {'type': 'end', 'processing_time': processing_time, 'metrics': {
            'response_length': len(full_text_response),
            'tts_chunks': total_chunks_generated,
            'first_token_latency': first_token_time - llm_start_time if first_token_time else None
        }}


@bp.route('/message', methods=['POST'])
@jwt_required()
def message():
    user_id = get_jwt_identity()
    data = request.json
    session_id = data.get('session_id')
    user_message_text = data.get('message')
    video_frame = data.get('video_frame')

    # IMPORTANT: Load the session object at the beginning of the request
    # This ensures it's bound to the current request's SQLAlchemy session.
    session = db.session.get(ChatSession, session_id) # Use db.session.get for primary key lookup
    if not session or int(session.user_id) != int(user_id):
        return jsonify({"error": "Session not found or access denied"}), 403

    # Add user message to DB immediately
    user_msg = ChatMessage(session_id=session.id, sender='user', message=user_message_text)
    db.session.add(user_msg)
    db.session.commit()
    
    # Invalidate chat history cache when new message is added
    if redis_client:
        try:
            cache_key = f"chat_history:{session.id}"
            redis_client.delete(cache_key)
        except Exception as e:
            logger.warning(f"Failed to invalidate chat history cache: {e}")

    # Create a placeholder AI message and get its ID.
    # We will update its 'message' field later in the 'finally' block of the generator.
    ai_msg_placeholder = ChatMessage(session_id=session.id, sender='ai', message="")
    db.session.add(ai_msg_placeholder)
    db.session.flush() # Flush to assign an ID to ai_msg_placeholder without committing the transaction yet.
    ai_message_id = ai_msg_placeholder.id # Store the ID for later retrieval

    # Accumulate the full AI reply text here
    full_ai_reply_text = []

    def event_stream(app_instance): # Accept app_instance as an argument
        nonlocal full_ai_reply_text # Declare intent to modify outer scope variable
        # Explicitly push an application context for the generator's lifetime
        app_context = app_instance.app_context() # Use the passed app_instance
        app_context.push()
        
        try:
            # Pass the actual app object to the streaming function
            for chunk in get_llm_and_tts_stream_from_openai(app_instance, user_message_text, video_frame, session_id):
                if chunk['type'] == 'text':
                    full_ai_reply_text.append(chunk['content'])
                    yield f"data: {json.dumps({'type': 'text', 'content': chunk['content']})}\n\n"
                elif chunk['type'] == 'audio':
                    yield f"data: {json.dumps({'type': 'audio', 'content': chunk['content']})}\n\n"
                elif chunk['type'] == 'end':
                    yield f"data: {json.dumps({'type': 'end', 'processing_time': chunk['processing_time']})}\n\n"
                elif chunk['type'] == 'error':
                    yield f"data: {json.dumps({'type': 'error', 'content': chunk['content']})}\n\n"
        except GeneratorExit:
            # This block is executed if the client disconnects prematurely
            logger.info("Client disconnected, generator closing.")
        finally:
            # This block ensures the AI message is saved and context is popped
            # The app_context is already pushed above, so db operations should work.
            ai_msg_to_update = db.session.get(ChatMessage, ai_message_id) # Use db.session.get for primary key lookup
            if ai_msg_to_update:
                ai_msg_to_update.message = "".join(full_ai_reply_text)
                db.session.commit()
                logger.info(f"AI message (ID: {ai_message_id}) updated in DB with full reply.")
                
                # Invalidate chat history cache after AI response
                if redis_client:
                    try:
                        cache_key = f"chat_history:{session_id}"
                        redis_client.delete(cache_key)
                    except Exception as e:
                        logger.warning(f"Failed to invalidate chat history cache after AI response: {e}")
            else:
                logger.error(f"Could not find AI message with ID {ai_message_id} to update.")
            
            db.session.remove() # Clean up the session
            app_context.pop() # Pop the context
            
    return Response(event_stream(current_app._get_current_object()), mimetype='text/event-stream') # Pass current_app here