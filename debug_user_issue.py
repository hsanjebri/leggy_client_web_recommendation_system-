#!/usr/bin/env python3
"""
Debug script to understand the user ID issue
"""

import requests
import json

def test_health():
    """Test API health"""
    try:
        response = requests.get("http://localhost:8000/health")
        print(f"Health Status: {response.status_code}")
        if response.status_code == 200:
            print("✅ API is healthy")
            return True
        else:
            print(f"❌ Health check failed: {response.json()}")
            return False
    except Exception as e:
        print(f"❌ Health check error: {e}")
        return False

def test_manual_reload():
    """Test manual reload"""
    try:
        response = requests.post("http://localhost:8000/reload/users")
        print(f"Reload Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Reload successful: {data}")
            return True
        else:
            print(f"❌ Reload failed: {response.json()}")
            return False
    except Exception as e:
        print(f"❌ Reload error: {e}")
        return False

def test_user_ids():
    """Test different user ID formats"""
    test_ids = [
        "68e6afde8c705a0dea7af92c",  # From your logs
        "68e6ada68c705a0dea7af92a",  # From your original request
        "685a7ca16f29de671ca83dcc",  # From available IDs in logs
    ]
    
    for user_id in test_ids:
        print(f"\n🔍 Testing user ID: {user_id}")
        try:
            response = requests.get("http://localhost:8000/recommendations/restaurants", 
                                 params={"user_id": user_id})
            print(f"  Status: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print(f"  ✅ Success: Found {len(data.get('RecommendedRestaurants', []))} restaurants")
            else:
                print(f"  ❌ Error: {response.json()}")
        except Exception as e:
            print(f"  ❌ Request error: {e}")

if __name__ == "__main__":
    print("🔍 Debugging User ID Issue")
    print("=" * 50)
    
    # Test API health
    if not test_health():
        print("❌ API is not healthy, stopping tests")
        exit(1)
    
    # Test manual reload
    print("\n🔄 Testing manual reload...")
    test_manual_reload()
    
    # Test different user IDs
    print("\n🧪 Testing different user IDs...")
    test_user_ids()
    
    print("\n📝 Analysis:")
    print("- If manual reload works but automatic doesn't, there's a code issue")
    print("- If no user IDs work, there might be a database connection issue")
    print("- If some user IDs work, it's a user existence issue")
