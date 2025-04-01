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
        "category": "linear",         # USDT Perpetuals
        "symbol": symbol,
        "side": side.upper(),         # "BUY" or "SELL"
        "orderType": "Market",
        "qty": qty,
        "timeInForce": "IOC",
        "reduceOnly": True
    }

    body_str = str(body).replace("'", '"').replace(" ", "")
    param_str = f"{timestamp}{BYBIT_API_KEY}{recv_window}{body_str}"
    sign = hmac.new(
        bytes(BYBIT_API_SECRET, "utf-8"),
        param_str.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()

    headers = {
        "X-BAPI-API-KEY": BYBIT_API_KEY,
        "X-BAPI-TIMESTAMP": timestamp,
        "X-BAPI-RECV-WINDOW": recv_window,
        "X-BAPI-SIGN": sign,
        "Content-Type": "application/json"
    }

    res = requests.post(url, headers=headers, json=body)
    print("📤 Bybit Response:", res.status_code, res.text)
    return res.status_code, res.text

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

    symbol = data.get("symbol")
    qty = data.get("qty")
    side = data.get("side")

    if not symbol or not qty or not side:
        return jsonify({"message": "Missing required parameters"}), 400

    print("✅ Webhook received. Sending order to Bybit...")
    code, response = send_bybit_order(symbol, side, qty)
    return jsonify({"message": "Order sent", "status": code, "response": response}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)


