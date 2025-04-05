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
import base64
import uuid
import smtplib
from email.mime.text import MIMEText
from flask import Flask, request, jsonify

app = Flask(__name__)

# ENV Variables
WEBHOOK_KEY = os.getenv("WEBHOOK_KEY")
BYBIT_API_KEY = os.getenv("BYBIT_API_KEY")
BYBIT_API_SECRET = os.getenv("BYBIT_API_SECRET")
BITGET_API_KEY = os.getenv("BITGET_API_KEY")
BITGET_API_SECRET = os.getenv("BITGET_API_SECRET")
BITGET_API_PASSPHRASE = os.getenv("BITGET_API_PASSPHRASE")
FALLBACK_EMAIL_USER = os.getenv("FALLBACK_EMAIL_USER")
FALLBACK_EMAIL_PASSWORD = os.getenv("FALLBACK_EMAIL_PASSWORD")

def get_timestamp():
    return str(int(time.time() * 1000))

def send_fallback_email(subject, body):
    smtp_server = "smtp.office365.com"
    smtp_port = 587
    recipient = "progel85@outlook.com"

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = FALLBACK_EMAIL_USER
    msg["To"] = recipient

    try:
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(FALLBACK_EMAIL_USER, FALLBACK_EMAIL_PASSWORD)
            server.sendmail(FALLBACK_EMAIL_USER, recipient, msg.as_string())
        print("📧 Email sent.")
    except Exception as e:
        print(f"[X] Failed to send email: {e}")

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
    res = requests.post(url, headers=headers, data=body_json)
    print("📤 Bybit Response:", res.status_code, res.text, flush=True)
    return res.status_code, res.text

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
        "clientOid": f"webhook-{uuid.uuid4().hex[:8]}",
        "reduceOnly": "YES",
        "tradeSide": "close"
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

    try:
        res = requests.post(url, headers=headers, data=body_json)
        print("📤 Bitget Response:", res.status_code, res.text, flush=True)

        if res.status_code != 200 or '"code":"00000"' not in res.text:
            send_fallback_email("❌ Bitget Order Failed", f"Request:\n{body_json}\n\nResponse:\n{res.text}")
        return res.status_code, res.text
    except Exception as e:
        send_fallback_email("❌ Bitget Exception", str(e))
        return 500, str(e)

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

    if not exchange or not symbol or not qty or not side:
        return jsonify({"message": "Missing parameters"}), 400

    if exchange == "bybit":
        print("✅ Sending to Bybit...")
        code, response = send_bybit_order(symbol, side, qty)
        return jsonify({"status": code, "response": response}), 200

    elif exchange == "bitget":
        print("✅ Sending to Bitget...")
        code, response = send_bitget_order(symbol, side, qty)
        return jsonify({"status": code, "response": response}), 200

    else:
        return jsonify({"message": "Exchange not supported"}), 400

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
