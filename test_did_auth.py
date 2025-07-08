# test_did_auth.py - Test your D-ID authentication

import os
import base64
import requests
from dotenv import load_dotenv

load_dotenv()

def test_did_auth():
    api_key = os.getenv("DID_API_KEY")
    
    if not api_key:
        print("❌ DID_API_KEY not found in .env file")
        return
    
    print(f"🔍 Testing D-ID API key: {api_key[:20]}...")
    
    # Encode credentials for Basic auth
    try:
        encoded_credentials = base64.b64encode(api_key.encode()).decode()
        print(f"🔑 Encoded credentials: {encoded_credentials[:20]}...")
        
        headers = {
            "Authorization": f"Basic {encoded_credentials}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        # Test with a simple API call to get credits
        response = requests.get(
            "https://api.d-id.com/credits",
            headers=headers,
            timeout=10
        )
        
        print(f"📊 Response Status: {response.status_code}")
        print(f"📊 Response: {response.text}")
        
        if response.status_code == 200:
            print("✅ D-ID authentication successful!")
            credits_data = response.json()
            print(f"💰 Your D-ID credits: {credits_data}")
        elif response.status_code == 401:
            print("❌ D-ID authentication failed - check your API key")
        else:
            print(f"⚠️ Unexpected response: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Error testing D-ID auth: {e}")

if __name__ == "__main__":
    test_did_auth()