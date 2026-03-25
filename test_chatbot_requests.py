#!/usr/bin/env python3
"""
Complete test script for the chatbot API using requests
"""

import requests
import json
import time

def test_chatbot_api():
    """Test the chatbot API with various messages"""
    
    # API endpoint
    base_url = "http://localhost:8001/chatbot"
    
    # Test data
    test_cases = [
        {
            "user_id": "6821cb90b5ce7f4dd4d2df0b",
            "message": "I want spicy food",
            "expected_keywords": ["spicy", "food"]
        },
        {
            "user_id": "6821cb90b5ce7f4dd4d2df0b", 
            "message": "Show me Italian cuisine",
            "expected_keywords": ["italian", "cuisine"]
        },
        {
            "user_id": "6821cb90b5ce7f4dd4d2df0b",
            "message": "I need burgers",
            "expected_keywords": ["burgers"]
        },
        {
            "user_id": "6821cb90b5ce7f4dd4d2df0b",
            "message": "I want something cheap",
            "expected_keywords": ["cheap"]
        },
        {
            "user_id": "6821cb90b5ce7f4dd4d2df0b",
            "message": "Pizza please",
            "expected_keywords": ["pizza"]
        }
    ]
    
    print("🤖 Testing Chatbot API...")
    print("=" * 60)
    print(f"API Endpoint: {base_url}")
    print("=" * 60)
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n🧪 Test {i}: '{test_case['message']}'")
        print("-" * 40)
        
        try:
            # Make the request
            response = requests.post(
                base_url,
                json={
                    "user_id": test_case["user_id"],
                    "message": test_case["message"]
                },
                headers={"Content-Type": "application/json"},
                timeout=10
            )
            
            # Check response status
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Status: {response.status_code}")
                print(f"📝 Keywords: {data.get('matched_keywords', [])}")
                print(f"📊 Results: {len(data.get('results', []))} items")
                
                # Check for errors
                if data.get('error'):
                    print(f"❌ Error: {data['error']}")
                elif data.get('message'):
                    print(f"ℹ️ Message: {data['message']}")
                else:
                    # Show results
                    results = data.get('results', [])
                    if results:
                        print("🍽️ Recommendations:")
                        for j, item in enumerate(results[:3], 1):  # Show first 3
                            print(f"  {j}. {item.get('name', 'N/A')}")
                            print(f"     Restaurant: {item.get('restaurant', 'N/A')}")
                            print(f"     Price: ${item.get('price', 'N/A')}")
                            print(f"     Rating: {item.get('rating', 'N/A')}")
                            print()
                    else:
                        print("ℹ️ No recommendations found")
                
            else:
                print(f"❌ HTTP Error: {response.status_code}")
                print(f"Response: {response.text}")
                
        except requests.exceptions.ConnectionError:
            print("❌ Connection Error: Make sure chatbot_api.py is running on port 8001")
            print("💡 Run: python chatbot_api.py")
            break
        except requests.exceptions.Timeout:
            print("❌ Timeout Error: Request took too long")
        except Exception as e:
            print(f"❌ Error: {str(e)}")
        
        # Small delay between requests
        time.sleep(0.5)
    
    print("\n" + "=" * 60)
    print("🎉 Testing completed!")

def test_individual_request():
    """Test a single request interactively"""
    base_url = "http://localhost:8001/chatbot"
    
    print("🔍 Interactive Test")
    print("=" * 30)
    
    while True:
        message = input("\nEnter your message (or 'quit' to exit): ")
        if message.lower() == 'quit':
            break
            
        try:
            response = requests.post(base_url, json={
                "user_id": "6821cb90b5ce7f4dd4d2df0b",
                "message": message
            })
            
            if response.status_code == 200:
                data = response.json()
                print(f"\n✅ Response:")
                print(json.dumps(data, indent=2))
            else:
                print(f"❌ Error: {response.status_code}")
                print(response.text)
                
        except Exception as e:
            print(f"❌ Error: {e}")

if __name__ == "__main__":
    print("Choose testing mode:")
    print("1. Run all test cases")
    print("2. Interactive testing")
    
    choice = input("Enter choice (1 or 2): ").strip()
    
    if choice == "1":
        test_chatbot_api()
    elif choice == "2":
        test_individual_request()
    else:
        print("Invalid choice. Running all test cases...")
        test_chatbot_api()
