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
import smtplib
import base64
import uuid
from email.mime.text import MIMEText
from flask import Flask, request, jsonify

app = Flask(__name__)

# ENV VARIABLES
WEBHOOK_KEY = os.getenv("WEBHOOK_KEY")
BYBIT_API_KEY = os.getenv("BYBIT_API_KEY")
BYBIT_API_SECRET = os.getenv("BYBIT_API_SECRET")
BITGET_API_KEY = os.getenv("BITGET_API_KEY")
BITGET_API_SECRET = os.getenv("BITGET_API_SECRET")
BITGET_API_PASSPHRASE = os.getenv("BITGET_API_PASSPHRASE")
OUTLOOK_EMAIL = os.getenv("OUTLOOK_EMAIL")
OUTLOOK_PASSWORD = os.getenv("OUTLOOK_PASSWORD")

def get_timestamp():
    return str(int(time.time() * 1000))

def send_email(subject, message):
    try:
        msg = MIMEText(message)
        msg['Subject'] = subject
        msg['From'] = OUTLOOK_EMAIL
        msg['To'] = OUTLOOK_EMAIL

        with smtplib.SMTP("smtp.office365.com", 587) as server:
            server.starttls()
            server.login(OUTLOOK_EMAIL, OUTLOOK_PASSWORD)
            server.send_message(msg)

        print("📧 Email sent.")
    except Exception as e:
        print("❌ Failed to send email:", e)

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
        BYBIT_API_SECRET.encode(), sign_payload.encode(), hashlib.sha256
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
    signature = hmac.new(BITGET_API_SECRET.encode(), pre_hash.encode(), hashlib.sha256).digest()
    signature_b64 = base64.b64encode(signature).decode()

    headers = {
        "ACCESS-KEY": BITGET_API_KEY,
        "ACCESS-SIGN": signature_b64,
        "ACCESS-TIMESTAMP": timestamp,
        "ACCESS-PASSPHRASE": BITGET_API_PASSPHRASE,
        "Content-Type": "application/json",
        "locale": "en-US"
    }

    response = requests.post(url, headers=headers, data=body_json)
    print("📤 Bitget Response:", response.status_code, response.text, flush=True)

    if response.status_code != 200 or '"code":"00000"' not in response.text:
        print("⚠️ Bitget order failed. Sending email fallback.")
        send_email("Bitget Order Fallback", f"Failed Bitget order:\n{body_json}\n\nResponse:\n{response.text}")

    return response.status_code, response.text

@app.route("/")
def home():
    return "Webhook bot is alive."

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json()
    print("📨 Incoming webhook:", data, flush=True)

    if not data or data.get("key") != WEBHOOK_KEY:
        print("[X] Invalid webhook key.", flush=True)
        return jsonify({"message": "Unauthorized"}), 401

    exchange = data.get("exchange")
    symbol = data.get("symbol")
    qty = data.get("qty")
    side = data.get("side")

    if not symbol or not qty or not side or not exchange:
        return jsonify({"message": "Missing required parameters"}), 400

    if exchange.lower() == "bybit":
        code, response = send_bybit_order(symbol, side, qty)
        return jsonify({"message": "Bybit order sent", "status": code, "response": response}), 200

    elif exchange.lower() == "bitget":
        code, response = send_bitget_order(symbol, side, qty)
        return jsonify({"message": "Bitget order sent", "status": code, "response": response}), 200

    else:
        return jsonify({"message": "Unsupported exchange"}), 400

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
