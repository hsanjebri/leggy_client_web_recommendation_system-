from flask import Flask, request, jsonify
from flask_cors import CORS
from chatbot_handler import get_recommendations_from_text
import pymongo

app = Flask(__name__)
# Restrictive and explicit CORS config for Angular dev server
CORS(
    app,
    resources={r"/*": {"origins": [
        "http://localhost:4200",
        "http://127.0.0.1:4200"
    ]}},
    supports_credentials=True,
    methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
    expose_headers=["Content-Type"]
)

@app.route("/chatbot", methods=["POST"])
def chatbot_endpoint():
    data = request.get_json()
    user_id = data.get("user_id")
    message = data.get("message")

    if not user_id or not message:
        return jsonify({"error": "Missing user_id or message"}), 400

    result = get_recommendations_from_text(message)
    return jsonify(result)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8001, debug=True)
