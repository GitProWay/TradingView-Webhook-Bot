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
import uuid
import base64
import smtplib
from flask import Flask, request, jsonify

app = Flask(__name__)

WEBHOOK_KEY = os.getenv("WEBHOOK_KEY")
BYBIT_API_KEY = os.getenv("BYBIT_API_KEY")
BYBIT_API_SECRET = os.getenv("BYBIT_API_SECRET")
BITGET_API_KEY = os.getenv("BITGET_API_KEY")
BITGET_API_SECRET = os.getenv("BITGET_API_SECRET")
BITGET_API_PASSPHRASE = os.getenv("BITGET_API_PASSPHRASE")

def get_timestamp():
    return str(int(time.time() * 1000))

def send_email_notification(subject, body):
    # Replace these if you'd like to enable email alerts (optional)
    to_email = "wraia@tuta.com"
    print(f"📧 Email Alert:\nSubject: {subject}\nBody: {body}")

def retry_request(send_func, *args):
    for attempt in range(3):
        code, response = send_func(*args)
        if code == 200:
            return code, response
        print(f"[X] Attempt {attempt+1}/3 failed: {response}")
        time.sleep(1)
    send_email_notification("⚠️ Webhook Order Failed", f"Payload: {args}\nError: {response}")
    return code, response

def send_bybit_order(symbol, side, qty):
    url = "https://api.bybit.com/v5/order/create"
    recv_window = "5000"
    timestamp = get_timestamp()

    body = {
        "category": "linear",
        "symbol": symbol,
        "side": side.capitalize(),
        "orderType": "Market",
        "qty": qty,
        "timeInForce": "IOC",
        "reduceOnly": True
    }

    body_json = json.dumps(body, separators=(',', ':'))
    sign_payload = f"{timestamp}{BYBIT_API_KEY}{recv_window}{body_json}"
    signature = hmac.new(bytes(BYBIT_API_SECRET, "utf-8"), sign_payload.encode("utf-8"), hashlib.sha256).hexdigest()

    headers = {
        "X-BAPI-API-KEY": BYBIT_API_KEY,
        "X-BAPI-TIMESTAMP": timestamp,
        "X-BAPI-RECV-WINDOW": recv_window,
        "X-BAPI-SIGN": signature,
        "Content-Type": "application/json"
    }

    print("📦 Bybit Body:", body_json, flush=True)
    response = requests.post(url, headers=headers, data=body_json)
    print("📤 Bybit Response:", response.status_code, response.text, flush=True)
    return response.status_code, response.text

def send_bitget_order(symbol, side, qty):
    url_path = "/api/v2/mix/order/place-order"
    url = f"https://api.bitget.com{url_path}"
    timestamp = get_timestamp()

    body = {
        "symbol": symbol,
        "marginCoin": "USDT",
        "marginMode": "isolated",
        "side": side.lower(),
        "orderType": "market",
        "size": qty,
        "productType": "USDT-FUTURES",
        "reduceOnly": "YES",
        "tradeSide": "close",
        "clientOid": f"webhook-{str(uuid.uuid4())[:8]}"
    }

    body_json = json.dumps(body, sort_keys=True, separators=(",", ":"))
    pre_hash = f"{timestamp}POST{url_path}{body_json}"
    print("🧪 Pre-hash string:", pre_hash, flush=True)

    signature = hmac.new(
        bytes(BITGET_API_SECRET, "utf-8"),
        pre_hash.encode("utf-8"),
        hashlib.sha256
    ).digest()
    signature_b64 = base64.b64encode(signature).decode()

    headers = {
        "ACCESS-KEY": BITGET_API_KEY,
        "ACCESS-SIGN": signature_b64,
        "ACCESS-TIMESTAMP": timestamp,
        "ACCESS-PASSPHRASE": BITGET_API_PASSPHRASE,
        "Content-Type": "application/json",
        "locale": "en-US"
    }

    print("📦 Bitget Body:", body_json, flush=True)
    response = requests.post(url, headers=headers, data=body_json)
    print("📤 Bitget Response:", response.status_code, response.text, flush=True)
    return response.status_code, response.text

@app.route("/")
def home():
    return "Webhook bot is alive."

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json()
    print("📨 Incoming webhook:", data, flush=True)

    if not data or data.get("key") != WEBHOOK_KEY:
        return jsonify({"message": "Unauthorized"}), 401

    exchange = data.get("exchange")
    symbol = data.get("symbol")
    qty = data.get("qty")
    side = data.get("side")

    if not symbol or not qty or not side or not exchange:
        return jsonify({"message": "Missing required parameters"}), 400

    if exchange == "bybit":
        print("✅ Webhook for Bybit received")
        code, response = retry_request(send_bybit_order, symbol, side, qty)
        return jsonify({"status": code, "response": response}), code
    elif exchange == "bitget":
        print("✅ Webhook for Bitget received")
        code, response = retry_request(send_bitget_order, symbol, side, qty)
        return jsonify({"status": code, "response": response}), code
    else:
        return jsonify({"message": "Exchange not supported"}), 400

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
