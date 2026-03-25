#!/usr/bin/env python3
"""
Test the fixed chatbot handler
"""

from chatbot_handler import get_recommendations_from_text

def test_chatbot_fix():
    """Test the chatbot with different messages"""
    
    test_messages = [
        "I want spicy food",
        "I'm looking for Italian cuisine", 
        "Show me burgers",
        "I want something cheap",
        "I need vegetarian options",
        "I want pizza"
    ]
    
    print("🤖 Testing Fixed Chatbot Handler...")
    print("=" * 50)
    
    for i, message in enumerate(test_messages, 1):
        print(f"\n{i}. Testing: '{message}'")
        print("-" * 30)
        
        try:
            result = get_recommendations_from_text(message)
            print(f"✅ Success!")
            print(f"Keywords found: {result.get('matched_keywords', [])}")
            print(f"Results: {len(result.get('results', []))} items")
            
            if result.get('error'):
                print(f"❌ Error: {result['error']}")
            elif result.get('message'):
                print(f"ℹ️ Message: {result['message']}")
            else:
                # Show first 3 results
                for j, item in enumerate(result.get('results', [])[:3], 1):
                    print(f"  {j}. {item.get('name', 'N/A')} - {item.get('restaurant', 'N/A')} (${item.get('price', 'N/A')})")
                    
        except Exception as e:
            print(f"❌ Error: {str(e)}")
    
    print("\n" + "=" * 50)
    print("Test completed!")

if __name__ == "__main__":
    test_chatbot_fix()
