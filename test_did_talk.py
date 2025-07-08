# test_did_talk.py - Test D-ID talk creation with different payloads

import os
import base64
import requests
from dotenv import load_dotenv

load_dotenv()

def test_did_talk():
    api_key = os.getenv("DID_API_KEY")
    
    if not api_key:
        print("❌ DID_API_KEY not found in .env file")
        return
    
    # Encode credentials for Basic auth
    encoded_credentials = base64.b64encode(api_key.encode()).decode()
    
    headers = {
        "Authorization": f"Basic {encoded_credentials}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    
    # Test different payload structures
    payloads_to_test = [
        {
            "name": "Minimal payload",
            "payload": {
                "script": {
                    "type": "text",
                    "input": "Hello, this is a test message."
                }
            }
        },
        {
            "name": "With source URL",
            "payload": {
                "script": {
                    "type": "text",
                    "input": "Hello, this is a test message."
                },
                "source_url": "https://d-id-public-bucket.s3.amazonaws.com/DefaultPresenters/Noelle_f/image.jpeg"
            }
        },
        {
            "name": "With voice provider",
            "payload": {
                "script": {
                    "type": "text",
                    "input": "Hello, this is a test message.",
                    "provider": {
                        "type": "microsoft",
                        "voice_id": "en-US-JennyNeural"
                    }
                }
            }
        }
    ]
    
    for test in payloads_to_test:
        print(f"\n🧪 Testing: {test['name']}")
        print(f"📋 Payload: {test['payload']}")
        
        try:
            response = requests.post(
                "https://api.d-id.com/talks",
                headers=headers,
                json=test['payload'],
                timeout=30
            )
            
            print(f"📊 Response Status: {response.status_code}")
            print(f"📊 Response: {response.text}")
            
            if response.status_code == 201:
                print(f"✅ Success with {test['name']}!")
                result = response.json()
                talk_id = result.get('id')
                if talk_id:
                    print(f"🎬 Talk ID: {talk_id}")
                return  # Stop on first success
            else:
                print(f"❌ Failed with {test['name']}")
                
        except Exception as e:
            print(f"❌ Exception with {test['name']}: {e}")
    
    print("\n🔍 All tests failed. Let's check API documentation...")

if __name__ == "__main__":
    test_did_talk()