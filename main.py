# ----------------------------------------------- #
# Plugin Name           : TradingView-Webhook-Bot #
# Author Name           : fabston                 #
# File Name             : main.py                 #
# ----------------------------------------------- #
from handler import send_alert
import os
import time
from flask import Flask, request, jsonify

app = Flask(__name__)

WEBHOOK_KEY = os.getenv("WEBHOOK_KEY")

def get_timestamp():
    return time.strftime("%Y-%m-%d %X")


@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.get_json(force=True)

        if not data:
            print("[X]", get_timestamp(), "No JSON received in webhook!")
            return jsonify({'message': 'No JSON received'}), 400

        print("📥 Received JSON:", data)

        if data.get("key") != WEBHOOK_KEY:
            print("[X]", get_timestamp(), "Wrong key in alert")
            return jsonify({'message': 'Unauthorized'}), 401

        print(get_timestamp(), "✅ Webhook received & key accepted.")
        print("✅ Test mode: Trade not executed (send_alert disabled).")
        return jsonify({'message': 'Webhook received successfully (test mode)'}), 200


    except Exception as e:
        print("[X]", get_timestamp(), "Unhandled error:\n>", e)
        return jsonify({'message': 'Error occurred'}), 400


@app.route("/")
def home():
    return "Webhook Bot is running!"
