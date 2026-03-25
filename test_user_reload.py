#!/usr/bin/env python3
"""
Test script to demonstrate the new user reload functionality.
This script shows how to handle new users without restarting the API.
"""

import requests
import json

# API base URL
BASE_URL = "http://localhost:8000"

def test_user_recommendations(user_id):
    """Test getting recommendations for a user"""
    print(f"\n🔍 Testing recommendations for user: {user_id}")
    
    # Test restaurant recommendations
    print("📋 Testing restaurant recommendations...")
    try:
        response = requests.get(f"{BASE_URL}/recommendations/restaurants", 
                              params={"user_id": user_id})
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Found {len(data.get('RecommendedRestaurants', []))} restaurant recommendations")
        else:
            print(f"❌ Error: {response.json()}")
    except Exception as e:
        print(f"❌ Request failed: {e}")
    
    # Test product recommendations
    print("\n🍽️ Testing product recommendations...")
    try:
        response = requests.get(f"{BASE_URL}/recommendations/products", 
                              params={"user_id": user_id})
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            total_products = sum(len(rest.get('products', [])) for rest in data.get('RecommendedProducts', []))
            print(f"✅ Found {total_products} product recommendations across {len(data.get('RecommendedProducts', []))} restaurants")
        else:
            print(f"❌ Error: {response.json()}")
    except Exception as e:
        print(f"❌ Request failed: {e}")

def test_manual_reload():
    """Test the manual reload endpoint"""
    print("\n🔄 Testing manual user data reload...")
    try:
        response = requests.post(f"{BASE_URL}/reload/users")
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ {data.get('message')} - User count: {data.get('user_count')}")
        else:
            print(f"❌ Error: {response.json()}")
    except Exception as e:
        print(f"❌ Request failed: {e}")

def test_health():
    """Test API health"""
    print("\n🏥 Testing API health...")
    try:
        response = requests.get(f"{BASE_URL}/health")
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            print("✅ API is healthy")
        else:
            print(f"❌ API health check failed: {response.json()}")
    except Exception as e:
        print(f"❌ Health check failed: {e}")

if __name__ == "__main__":
    print("🚀 Testing User Reload Functionality")
    print("=" * 50)
    
    # Test API health first
    test_health()
    
    # Test with the specific user ID
    user_id = "68e6ada68c705a0dea7af92a"
    test_user_recommendations(user_id)
    
    # Test manual reload
    test_manual_reload()
    
    # Test again after reload
    print("\n🔄 Testing again after manual reload...")
    test_user_recommendations(user_id)
    
    print("\n✨ Test completed!")
    print("\n📝 Usage Instructions:")
    print("1. When you add a new user to the database, the API will automatically try to reload user data")
    print("2. If automatic reload fails, you can manually call: POST http://localhost:8000/reload/users")
    print("3. No need to restart the API server!")
