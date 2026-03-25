#!/usr/bin/env python3
"""
Startup script for the chatbot API with error checking
"""

import sys
import traceback

def check_dependencies():
    """Check if all required modules are available"""
    try:
        import flask
        import pandas
        import pymongo
        import difflib
        import unicodedata
        import re
        print("✅ All dependencies are available")
        return True
    except ImportError as e:
        print(f"❌ Missing dependency: {e}")
        print("💡 Install with: pip install flask pandas pymongo")
        return False

def test_chatbot_handler():
    """Test the chatbot handler before starting the API"""
    try:
        from chatbot_handler import get_recommendations_from_text
        print("✅ Chatbot handler imported successfully")
        
        # Test with a simple message
        result = get_recommendations_from_text("test")
        print("✅ Chatbot handler function works")
        return True
    except Exception as e:
        print(f"❌ Error in chatbot handler: {e}")
        traceback.print_exc()
        return False

def start_api():
    """Start the Flask API"""
    try:
        from chatbot_api import app
        print("✅ Starting chatbot API on http://localhost:8001")
        print("💡 Press Ctrl+C to stop the server")
        app.run(host="0.0.0.0", port=8001, debug=True)
    except Exception as e:
        print(f"❌ Error starting API: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    print("🤖 Legy Chatbot API Startup")
    print("=" * 40)
    
    # Check dependencies
    if not check_dependencies():
        sys.exit(1)
    
    # Test chatbot handler
    if not test_chatbot_handler():
        print("\n❌ Cannot start API due to chatbot handler errors")
        sys.exit(1)
    
    # Start the API
    print("\n🚀 Starting API server...")
    start_api()
