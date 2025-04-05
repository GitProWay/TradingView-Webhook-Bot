# ----------------------------------------------- #
# Plugin Name           : TradingView-Webhook-Bot #
# Author Name           : fabston + ChatGPT       #
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
from flask import Flask, request, jsonify
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import uuid

app = Flask(__name__)

WEBHOOK_KEY = os.getenv("WEBHOOK_KEY")
BITGET_API_KEY = os.getenv("BITGET_API_KEY")
BITGET_API_SECRET = os.getenv("BITGET_API_SECRET")
BITGET_API_PASSPHRASE = os.getenv("BITGET_API_PASSPHRASE")

OUTLOOK_EMAIL = os.getenv("OUTLOOK_EMAIL")
OUTLOOK_APP_PASSWORD = os.getenv("OUTLOOK_APP_PASSWORD")

def get_timestamp():
    return str(int(time.time() * 1000))

def send_email(subject, body):
    try:
        msg = MIMEMultipart()
        msg['From'] = OUTLOOK_EMAIL
        msg['To'] = OUTLOOK_EMAIL
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))

        server = smtplib.SMTP("smtp.office365.com", 587)
        server.starttls()
        server.login(OUTLOOK_EMAIL, OUTLOOK_APP_PASSWORD)
        server.send_message(msg)
        server.quit()
        print("📧 Fallback email sent successfully.", flush=True)
    except Exception as e:
        print(f"[X] Failed to send fallback email: {e}", flush=True)

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
        "clientOid": f"webhook-{str(uuid.uuid4())[:8]}",
        "reduceOnly": "YES",
        "tradeSide": "close"
    }

    body_json = json.dumps(body, sort_keys=True, separators=(",", ":"))
    pre_hash = f"{timestamp}POST{url_path}{body_json}"
    print("🧪 Pre-hash string:", pre_hash, flush=True)

    signature = hmac.new(
        BITGET_API_SECRET.encode("utf-8"),
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

    if response.status_code != 200 or '"code":"' in response.text and not '"code":"00000"' in response.text:
        print("[X] Initial Bitget order failed. Trying fallback retry...", flush=True)

        # Retry once
        timestamp_retry = get_timestamp()
        body["clientOid"] = f"webhook-{str(uuid.uuid4())[:8]}"
        body_json_retry = json.dumps(body, sort_keys=True, separators=(",", ":"))
        pre_hash_retry = f"{timestamp_retry}POST{url_path}{body_json_retry}"
        signature_retry = base64.b64encode(hmac.new(
            BITGET_API_SECRET.encode("utf-8"),
            pre_hash_retry.encode("utf-8"),
            hashlib.sha256
        ).digest()).decode()

        headers["ACCESS-TIMESTAMP"] = timestamp_retry
        headers["ACCESS-SIGN"] = signature_retry

        response_retry = requests.post(url, headers=headers, data=body_json_retry)
        print("📤 Retry Bitget Response:", response_retry.status_code, response_retry.text, flush=True)

        if response_retry.status_code != 200 or '"code":"' in response_retry.text and not '"code":"00000"' in response_retry.text:
            subject = f"[TRADE FAILED] Bitget close order for {symbol.upper()}"
            body_text = f"""Initial and retry Bitget order failed.

Symbol: {symbol}
Side: {side}
Qty: {qty}
Error: {response_retry.text}"""
            send_email(subject, body_text)

    return response.status_code, response.text

@app.route("/")
def home():
    return "Webhook bot is alive."

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json()
    print("📨 Incoming webhook:", data, flush=True)

    if not data or data.get("key") != WEBHOOK_KEY:
        return jsonify({"message": "Unauthorized or no data"}), 401

    exchange = data.get("exchange")
    symbol = data.get("symbol")
    qty = data.get("qty")
    side = data.get("side")

    if not symbol or not qty or not side or not exchange:
        return jsonify({"message": "Missing required parameters"}), 400

    if exchange == "bitget":
        print("✅ Sending to Bitget...", flush=True)
        code, response = send_bitget_order(symbol, side, qty)
        return jsonify({"message": "Bitget order attempted", "status": code, "response": response}), 200

    return jsonify({"message": "Unsupported exchange"}), 400

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
