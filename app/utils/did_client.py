import requests
import os
from dotenv import load_dotenv
import time
import base64

load_dotenv()

class DIDClient:
    def __init__(self):
        self.api_key = os.getenv("DID_API_KEY")
        self.base_url = "https://api.d-id.com"
        
        if not self.api_key:
            print("❌ Warning: DID_API_KEY not found in environment variables")
            return
        
        # D-ID uses Basic auth with base64 encoding of the API key
        try:
            # Encode the API key for Basic authentication
            encoded_credentials = base64.b64encode(self.api_key.encode()).decode()
            
            self.headers = {
                "Authorization": f"Basic {encoded_credentials}",
                "Content-Type": "application/json",
                "Accept": "application/json"
            }
            print(f"✅ D-ID Client initialized with API key: {self.api_key[:10]}...")
        except Exception as e:
            print(f"❌ Error encoding D-ID credentials: {e}")
            return
    
    def create_talk(self, text, avatar_image_url=None):
        """Create a talking avatar video from text"""
        if not self.api_key:
            print("❌ D-ID API key not configured")
            return None
        
        # Limit text length for D-ID
        if len(text) > 500:
            text = text[:500] + "..."
        
        # WORKING: Minimal payload structure that actually works
        payload = {
            "script": {
                "type": "text",
                "input": text
            }
        }
        
        try:
            print(f"🎬 Creating D-ID talk with text: {text[:50]}...")
            
            response = requests.post(
                f"{self.base_url}/talks",
                headers=self.headers,
                json=payload,
                timeout=30
            )
            
            print(f"D-ID Response Status: {response.status_code}")
            print(f"D-ID Response: {response.text[:200]}...")
            
            if response.status_code == 201:
                result = response.json()
                print(f"✅ D-ID talk created successfully: {result.get('id')}")
                return result
            else:
                print(f"D-ID API Error: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            print(f"D-ID API Exception: {e}")
            return None
    
    def get_talk_status(self, talk_id):
        """Check the status of a talk generation"""
        if not self.api_key:
            return None
            
        try:
            response = requests.get(
                f"{self.base_url}/talks/{talk_id}",
                headers=self.headers,
                timeout=10
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                print(f"D-ID Status Error: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            print(f"D-ID Status Exception: {e}")
            return None
    
    def wait_for_completion(self, talk_id, max_wait=60):
        """Wait for talk generation to complete"""
        if not self.api_key:
            return None
            
        start_time = time.time()
        
        while time.time() - start_time < max_wait:
            status_response = self.get_talk_status(talk_id)
            
            if not status_response:
                return None
            
            status = status_response.get('status')
            print(f"D-ID Status: {status}")
            
            if status == 'done':
                return status_response
            elif status == 'error':
                print(f"D-ID Error: {status_response.get('error', 'Unknown error')}")
                return None
            
            time.sleep(2)
        
        print("D-ID: Timeout waiting for completion")
        return None

# Helper function for easy use in routes
def create_talking_avatar(text, avatar_url=None):
    """Create a talking avatar video and return the video URL"""
    client = DIDClient()
    
    if not client.api_key:
        print("❌ D-ID API key not configured, skipping avatar generation")
        return None
    
    # Create the talk
    talk_response = client.create_talk(text, avatar_url)
    if not talk_response:
        return None
    
    talk_id = talk_response.get('id')
    if not talk_id:
        return None
    
    print(f"🎬 D-ID Talk created with ID: {talk_id}, waiting for completion...")
    
    # Wait for completion
    completed_response = client.wait_for_completion(talk_id)
    if not completed_response:
        return None
    
    # Return the video URL
    video_url = completed_response.get('result_url')
    if video_url:
        print(f"✅ D-ID Video ready: {video_url}")
    return video_url