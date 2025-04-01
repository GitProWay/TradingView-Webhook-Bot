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
    timestamp = time.strftime("%Y-%m-%d %X")
    return timestamp


@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.get_json()

        if data.get("key") != WEBHOOK_KEY:
            print("[X]", get_timestamp(), "Alert Received & Refused! (Wrong Key)")
            return jsonify({'message': 'Unauthorized'}), 401

        print(get_timestamp(), "Alert Received & Sent!")
        send_alert(data)
        return jsonify({'message': 'Webhook received successfully'}), 200

    except Exception as e:
        print("[X]", get_timestamp(), "Error:\n>", e)
        return jsonify({'message': 'Error'}), 400


if __name__ == "__main__":
    from waitress import serve
    serve(app, host="0.0.0.0", port=8080)

