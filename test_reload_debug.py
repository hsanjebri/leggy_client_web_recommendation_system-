#!/usr/bin/env python3
"""
Debug script to test the reload functionality
"""

import requests
import json

def test_reload_manually():
    """Test manual reload endpoint"""
    print("🔄 Testing manual reload...")
    try:
        response = requests.post("http://localhost:8000/reload/users")
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}")
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_user_with_reload(user_id):
    """Test user with detailed logging"""
    print(f"\n🔍 Testing user: {user_id}")
    try:
        response = requests.get(f"http://localhost:8000/recommendations/restaurants", 
                              params={"user_id": user_id})
        print(f"Status: {response.status_code}")
        if response.status_code != 200:
            print(f"Error: {response.json()}")
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    print("🧪 Testing Reload Debug")
    print("=" * 40)
    
    # Test the specific user ID from the logs
    user_id = "68e6afde8c705a0dea7af92c"
    
    print("1. Testing manual reload first...")
    test_reload_manually()
    
    print("\n2. Testing user after manual reload...")
    test_user_with_reload(user_id)
    
    print("\n3. Testing user again (should work now)...")
    test_user_with_reload(user_id)






