#!/usr/bin/env python3
"""
Quick test to verify the chatbot API is working
"""

import requests
import time

def test_api_connection():
    """Test if the API is running and responding"""
    try:
        print("🔍 Testing API connection...")
        response = requests.get("http://localhost:8001", timeout=5)
        print(f"✅ API is running! Status: {response.status_code}")
        return True
    except requests.exceptions.ConnectionError:
        print("❌ API is not running on port 8001")
        print("💡 Start it with: python start_chatbot.py")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_chatbot_endpoint():
    """Test the chatbot endpoint"""
    try:
        print("🤖 Testing chatbot endpoint...")
        response = requests.post(
            "http://localhost:8001/chatbot",
            json={
                "user_id": "6821cb90b5ce7f4dd4d2df0b",
                "message": "I want spicy food"
            },
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            print("✅ Chatbot endpoint working!")
            print(f"📝 Keywords: {data.get('matched_keywords', [])}")
            print(f"📊 Results: {len(data.get('results', []))} items")
            return True
        else:
            print(f"❌ API returned status {response.status_code}")
            print(f"Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error testing chatbot: {e}")
        return False

if __name__ == "__main__":
    print("🧪 Quick API Test")
    print("=" * 30)
    
    # Test connection
    if test_api_connection():
        # Test chatbot endpoint
        test_chatbot_endpoint()
    
    print("\n" + "=" * 30)
    print("Test completed!")
