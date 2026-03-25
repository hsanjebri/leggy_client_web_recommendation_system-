#!/usr/bin/env python3
"""
Test script for the chatbot API
"""

import requests
import json

def test_chatbot():
    """Test the chatbot with different messages"""
    
    # Test messages
    test_messages = [
        "I want spicy food",
        "I'm looking for Italian cuisine",
        "Show me burgers",
        "I want something cheap",
        "I need vegetarian options",
        "I want pizza"
    ]
    
    base_url = "http://localhost:8001/chatbot"
    user_id = "6821cb90b5ce7f4dd4d2df0b"  # Use a real user ID from your database
    
    print("🤖 Testing Chatbot API...")
    print("=" * 50)
    
    for i, message in enumerate(test_messages, 1):
        print(f"\n{i}. Testing: '{message}'")
        print("-" * 30)
        
        try:
            response = requests.post(base_url, json={
                'user_id': user_id,
                'message': message
            }, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Success!")
                print(f"Keywords found: {data.get('matched_keywords', [])}")
                print(f"Results: {len(data.get('results', []))} items")
                
                # Show first 3 results
                for j, result in enumerate(data.get('results', [])[:3], 1):
                    print(f"  {j}. {result.get('name', 'N/A')} - {result.get('restaurant', 'N/A')} (${result.get('price', 'N/A')})")
                    
            else:
                print(f"❌ Error: {response.status_code}")
                print(f"Response: {response.text}")
                
        except requests.exceptions.ConnectionError:
            print("❌ Connection Error: Make sure chatbot_api.py is running on port 8001")
            break
        except Exception as e:
            print(f"❌ Error: {str(e)}")
    
    print("\n" + "=" * 50)
    print("Test completed!")

if __name__ == "__main__":
    test_chatbot()
