#!/bin/bash
# Test script for chatbot API using curl

echo "🤖 Testing Chatbot API with curl"
echo "================================="

# Test 1: Spicy food
echo "Test 1: Spicy food"
curl -X POST http://localhost:8001/chatbot \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "6821cb90b5ce7f4dd4d2df0b",
    "message": "I want spicy food"
  }' | python -m json.tool

echo -e "\n" 

# Test 2: Italian cuisine
echo "Test 2: Italian cuisine"
curl -X POST http://localhost:8001/chatbot \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "6821cb90b5ce7f4dd4d2df0b",
    "message": "Show me Italian cuisine"
  }' | python -m json.tool

echo -e "\n"

# Test 3: Burgers
echo "Test 3: Burgers"
curl -X POST http://localhost:8001/chatbot \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "6821cb90b5ce7f4dd4d2df0b",
    "message": "I need burgers"
  }' | python -m json.tool

echo -e "\n"

# Test 4: Pizza
echo "Test 4: Pizza"
curl -X POST http://localhost:8001/chatbot \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "6821cb90b5ce7f4dd4d2df0b",
    "message": "Pizza please"
  }' | python -m json.tool

echo -e "\n"
echo "✅ All tests completed!"
