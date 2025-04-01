# ----------------------------------------------- #
# Plugin Name           : TradingView-Webhook-Bot #
# Author Name           : fabston                 #
# File Name             : main.py                 #
# ----------------------------------------------- #
# ----------------------------------------------- #
# Plugin Name           : TradingView-Webhook-Bot #
# Author Name           : fabston                 #
# File Name             : main.py                 #
# ----------------------------------------------- #

import os
import time
import hmac
import hashlib
import requests
import json
from flask import Flask, request, jsonify

app = Flask(__name__)

WEBHOOK_KEY = os.getenv("WEBHOOK_KEY")
BYBIT_API_KEY = os.getenv("BYBIT_API_KEY")
BYBIT_API_SECRET = os.getenv("BYBIT_API_SECRET")

def get_timestamp():
    return str(int(time.time() * 1000))

def send_bybit_order(symbol, side, qty):
    url = "https://api.bybit.com/v5/order/create"
    recv_window = "5000"
    timestamp = get_timestamp()

    body = {
        "category": "linear",
        "symbol": symbol,
        "side": side.upper(),
        "orderType": "Market",
        "qty": qty,
        "timeInForce": "IOC",
        "reduceOnly": True
    }

    body_json = json.dumps(body, separators=(',', ':'))
    sign_payload = f"{timestamp}{BYBIT_API_KEY}{recv_window}{body_json}"

    signature = hmac.new(
        bytes(BYBIT_API_SECRET, "utf-8"),
        sign_payload.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()

    headers = {
        "X-BAPI-API-KEY": BYBIT_API_KEY,
        "X-BAPI-TIMESTAMP": timestamp,
        "X-BAPI-RECV-WINDOW": recv_window,
        "X-BAPI-SIGN": signature,
        "Content-Type": "application/json"
    }

    response = requests.post(url, headers=headers, data=body_json)
    print("📤 Bybit Response:", response.status_code, response.text, flush=True)
    return response.status_code, response.text

@app.route("/")
def home():
    return "Webhook bot is alive."

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json()
    print("📨 Incoming webhook:", data, flush=True)

    if not data:
        return jsonify({"message": "No data received"}), 400

    if data.get("key") != WEBHOOK_KEY:
        print("[X] Wrong key", flush=True)
        return jsonify({"message": "Unauthorized"}), 401

    exchange = data.get("exchange")
    symbol = data.get("symbol")
    qty = data.get("qty")
    side = data.get("side")

    if not symbol or not qty or not side or not exchange:
        return jsonify({"message": "Missing required parameters"}), 400

    if exchange == "bybit":
        print("✅ Webhook received for Bybit. Sending order...", flush=True)
        code, response = send_bybit_order(symbol, side, qty)
        return jsonify({"message": "Order sent to Bybit", "status": code, "response": response}), 200
    else:
        print("[X] Unsupported exchange:", exchange, flush=True)
        return jsonify({"message": "Exchange not supported"}), 400

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)




