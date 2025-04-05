# ----------------------------------------------- #
# Plugin Name           : TradingView-Webhook-Bot #
# Author Name           : fabston + ProGPT        #
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
from email.mime.text import MIMEText
from flask import Flask, request, jsonify

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
    try:
        msg = MIMEText(body, "html")
        msg["Subject"] = subject
        msg["From"] = EMAIL_ADDRESS
        msg["To"] = EMAIL_ADDRESS

        with smtplib.SMTP(EMAIL_HOST, EMAIL_PORT) as server:
            server.ehlo()
            server.starttls()
            server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            server.send_message(msg)

        print("📧 Fallback email sent successfully.", flush=True)

    except Exception as e:
        print("❌ Fallback email failed to send:\n", e, flush=True)

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

    print("📦 Final Bybit request body:", body_json, flush=True)
    response = requests.post(url, headers=headers, data=body_json)
    print("📤 Bybit Response:", response.status_code, response.text, flush=True)
    return response.status_code, response.text

def send_bitget_order(symbol, side, qty):
    import uuid
    url_path = "/api/v2/mix/order/place-order"
    url = f"https://api.bitget.com{url_path}"
    timestamp = get_timestamp()

    body = {
        "clientOid": f"webhook-{str(uuid.uuid4())[:8]}",
        "symbol": symbol,
        "marginCoin": "USDT",
        "marginMode": "isolated",
        "orderType": "market",
        "productType": "USDT-FUTURES",
        "reduceOnly": "YES",
        "tradeSide": "close",
        "side": side.lower(),
        "size": qty
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
    print("🧠 Headers:", headers, flush=True)

    response = requests.post(url, headers=headers, data=body_json)
    print("📤 Bitget Response:", response.status_code, response.text, flush=True)
    return response.status_code, response.text

def send_bitget_order_with_fallback(symbol, side, qty):
    print("✅ Sending to Bitget...", flush=True)
    code, response = send_bitget_order(symbol, side, qty)

    if code == 200 and '"code":"00000"' in response:
        return code, response

    print("❌ Initial Bitget order failed. Trying fallback retry...", flush=True)
    retry_code, retry_response = send_bitget_order(symbol, side, qty)

    if retry_code == 200 and '"code":"00000"' in retry_response:
        return retry_code, retry_response

    print("📧 Attempting to send fallback email...", flush=True)
    html = f"""
    <h3>⚠️ Fallback Alert!</h3>
    <p>Your Bitget order failed twice.</p>
    <p>📍 <strong>Symbol:</strong> {symbol}<br>
    📍 <strong>Side:</strong> {side}<br>
    📍 <strong>Quantity:</strong> {qty}</p>
    <p>❌ <strong>Initial Error:</strong><br><code>{response}</code></p>
    <p>❌ <strong>Retry Error:</strong><br><code>{retry_response}</code></p>
    """
    send_email("[Webhook Alert] Bitget Order Failed Twice", html)

    return retry_code, retry_response

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

    elif exchange == "bitget":
        print("✅ Webhook received for Bitget. Sending order...", flush=True)
        code, response = send_bitget_order_with_fallback(symbol, side, qty)
        return jsonify({"message": "Order sent to Bitget", "status": code, "response": response}), 200

    else:
        print("[X] Unsupported exchange:", exchange, flush=True)
        return jsonify({"message": "Exchange not supported"}), 400

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
