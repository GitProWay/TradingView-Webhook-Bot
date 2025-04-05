# ----------------------------------------------- #
# Plugin Name           : TradingView-Webhook-Bot #
# Author Name           : fabston (modified)      #
# File Name             : main.py                 #
# ----------------------------------------------- #

import os
import time
import hmac
import hashlib
import requests
import json
import base64
import smtplib
import uuid
from flask import Flask, request, jsonify
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

app = Flask(__name__)

# Environment Variables
WEBHOOK_KEY = os.getenv("WEBHOOK_KEY")
BYBIT_API_KEY = os.getenv("BYBIT_API_KEY")
BYBIT_API_SECRET = os.getenv("BYBIT_API_SECRET")
BITGET_API_KEY = os.getenv("BITGET_API_KEY")
BITGET_API_SECRET = os.getenv("BITGET_API_SECRET")
BITGET_API_PASSPHRASE = os.getenv("BITGET_API_PASSPHRASE")
EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
EMAIL_HOST = os.getenv("EMAIL_HOST")
EMAIL_PORT = int(os.getenv("EMAIL_PORT"))

def get_timestamp():
    return str(int(time.time() * 1000))

def send_email(subject, body):
    msg = MIMEMultipart()
    msg["From"] = EMAIL_ADDRESS
    msg["To"] = EMAIL_ADDRESS
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP(EMAIL_HOST, EMAIL_PORT) as server:
            server.starttls()
            server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            server.sendmail(EMAIL_ADDRESS, EMAIL_ADDRESS, msg.as_string())
            print("✅ Fallback email sent.")
    except Exception as e:
        print("❌ Fallback email failed to send:")
        print("[Error]", str(e))

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
    signature = hmac.new(BYBIT_API_SECRET.encode(), sign_payload.encode(), hashlib.sha256).hexdigest()

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
        BITGET_API_SECRET.encode(),
        pre_hash.encode(),
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
    print("🧠 Headers:", headers, flush=True)
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
        print("[X] Unauthorized or no data", flush=True)
        return jsonify({"message": "Unauthorized or invalid request"}), 401

    exchange = data.get("exchange")
    symbol = data.get("symbol")
    qty = data.get("qty")
    side = data.get("side")

    if not all([exchange, symbol, qty, side]):
        return jsonify({"message": "Missing required fields"}), 400

    if exchange == "bybit":
        print("✅ Sending to Bybit...", flush=True)
        code, response = send_bybit_order(symbol, side, qty)
        return jsonify({"message": "Order sent to Bybit", "status": code, "response": response}), 200

    elif exchange == "bitget":
        print("✅ Sending to Bitget...", flush=True)
        code, response = send_bitget_order(symbol, side, qty)

        if code != 200 or '"code":"00000"' not in response:
            print("[X] Initial Bitget order failed. Trying fallback retry...", flush=True)
            code2, response2 = send_bitget_order(symbol, side, qty)

            if code2 != 200 or '"code":"00000"' not in response2:
                subject = "[Webhook Alert] Bitget Order Failed Twice"
                body = f"""
⚠️ Fallback Alert!

Your Bitget order failed twice.

📍 Symbol: {symbol}
📍 Side: {side}
📍 Quantity: {qty}

❌ Initial Error:
{response}

❌ Retry Error:
{response2}
"""
                send_email(subject, body)

        return jsonify({"message": "Order sent to Bitget", "status": code, "response": response}), 200

    else:
        print("[X] Unsupported exchange:", exchange, flush=True)
        return jsonify({"message": "Exchange not supported"}), 400

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
