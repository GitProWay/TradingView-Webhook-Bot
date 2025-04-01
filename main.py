# ----------------------------------------------- #
# Plugin Name           : TradingView-Webhook-Bot #
# Author Name           : fabston                 #
# File Name             : main.py                 #
# ----------------------------------------------- #
import os
from flask import Flask, request, jsonify

app = Flask(__name__)

WEBHOOK_KEY = os.getenv("WEBHOOK_KEY")

@app.route("/")
def home():
    return "Webhook bot is alive."

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json()

    if not data:
        return jsonify({"message": "No data received"}), 400

    if data.get("key") != WEBHOOK_KEY:
        return jsonify({"message": "Unauthorized"}), 401

    print("✅ Webhook received:", data)
    return jsonify({"message": "Success"}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)

