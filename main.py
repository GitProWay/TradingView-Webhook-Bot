# ----------------------------------------------- #
# Plugin Name           : TradingView-Webhook-Bot #
# Author Name           : fabston + ProGPT        #
# File Name             : main.py (Final Retry & Notification Control) #
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
SIMULATE_FAILURE = os.getenv("SIMULATE_FAILURE", "False").lower() == "true"

print(f"🚀 Webhook Bot Started. SIMULATE_FAILURE: {SIMULATE_FAILURE}", flush=True)

def get_timestamp():
    return str(int(time.time() * 1000))

def send_email(subject, body):
    try:
        msg = MIMEText(body, "html")
        msg["Subject"] = subject
        msg["From"] = EMAIL_ADDRESS
        msg["To"] = EMAIL_ADDRESS

        with smtplib.SMTP(EMAIL_HOST, EMAIL_PORT) as server:
            server.starttls()
            server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            server.send_message(msg)

        print("📧 Email sent successfully.", flush=True)
    except Exception as e:
        print("❌ Email failed to send:", e, flush=True)

def check_position_open(exchange, symbol):
    # Placeholder for real position check. Always returns True for now.
    # You can implement real API calls here if the exchange supports it.
    return True

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

    response = requests.post(url, headers=headers, data=body_json)
    return response.status_code, response.text

def send_bitget_order(symbol, side, qty):
    import uuid
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
        "reduceOnly": "YES"
    }

    body_json = json.dumps(body, sort_keys=True, separators=(",", ":"))
    pre_hash = f"{timestamp}POST{url_path}{body_json}"

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

    response = requests.post(url, headers=headers, data=body_json)
    return response.status_code, response.text

def close_position_with_retry(exchange, symbol, side, qty):
    attempt = 0
    simulation_failures_remaining = 5 if SIMULATE_FAILURE else 0

    while True:
        attempt += 1

        # Check position before attempting to close again
        if not check_position_open(exchange, symbol):
            print(f"✅ Position already closed. Exiting retry loop at attempt #{attempt}", flush=True)
            return

        if simulation_failures_remaining > 0:
            print(f"🧪 [Simulated Failure] Attempt {attempt}", flush=True)
            simulation_failures_remaining -= 1
            status_code, response = 500, "Simulated failure"
        else:
            print(f"🔁 Attempt {attempt} to close position on {exchange}...", flush=True)
            if exchange == "bybit":
                status_code, response = send_bybit_order(symbol, side, qty)
            elif exchange == "bitget":
                status_code, response = send_bitget_order(symbol, side, qty)
            else:
                print("❌ Unsupported exchange for retry.", flush=True)
                return

        if status_code == 200 and ('"code":"00000"' in response or '"retCode":0' in response):
            print(f"✅ Position successfully closed on attempt #{attempt}", flush=True)
            subject = f"[Webhook Alert] Trade Closed on Attempt #{attempt}"
            body = f"<p>Position for <strong>{symbol}</strong> was successfully closed on attempt #{attempt}.</p>"
            send_email(subject, body)
            return

        # Send notifications at key milestones
        if attempt in [50, 500, 1000, 5000]:
            subject = f"[Webhook Alert] {attempt} Attempts Reached"
            body = f"<p>Tried to close position {attempt} times for <strong>{symbol}</strong> without success.</p>"
            send_email(subject, body)

        time.sleep(0.2)  # 5 retries per second

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
        return jsonify({"message": "Unauthorized"}), 401

    exchange = data.get("exchange")
    symbol = data.get("symbol")
    qty = data.get("qty")
    side = data.get("side")

    if not all([exchange, symbol, qty, side]):
        return jsonify({"message": "Missing required parameters"}), 400

    if exchange in ["bybit", "bitget"]:
        close_position_with_retry(exchange, symbol, side, qty)
        return jsonify({"message": f"{exchange} order executed with retry logic."}), 200

    return jsonify({"message": "Exchange not supported."}), 400

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
