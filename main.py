# ----------------------------------------------- #
# Plugin Name           : TradingView-Webhook-Bot #
# Author Name           : fabston + ProGPT        #
# File Name             : main.py (Complete Version with Simulated Failure) #
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
    if SIMULATE_FAILURE:
        print("🚧 SIMULATE_FAILURE is ON. Forcing position as OPEN.", flush=True)
        return True

    print(f"🔍 Checking position status for {exchange} - {symbol}", flush=True)
    try:
        if exchange == "bybit":
            url = "https://api.bybit.com/v5/position/list"
            api_timestamp = get_timestamp()
            params = {
                "category": "linear",
                "symbol": symbol,
                "api_key": BYBIT_API_KEY,
                "timestamp": api_timestamp
            }
            param_string = f"api_key={BYBIT_API_KEY}&category=linear&symbol={symbol}&timestamp={api_timestamp}"
            sign = hmac.new(
                bytes(BYBIT_API_SECRET, "utf-8"),
                param_string.encode("utf-8"),
                hashlib.sha256
            ).hexdigest()

            params["sign"] = sign

            response = requests.get(url, params=params)
            data = response.json()
            print(f"📖 Bybit Position Response: {data}", flush=True)
            return any(pos.get("size", "0") != "0" for pos in data.get("result", {}).get("list", []))

        elif exchange == "bitget":
            url = "https://api.bitget.com/api/v2/mix/position/single-position"
            timestamp = get_timestamp()

            params = {
                "symbol": symbol,
                "marginCoin": "USDT",
                "productType": "USDT-FUTURES"
            }

            params_string = f"symbol={symbol}&marginCoin=USDT&productType=USDT-FUTURES"
            pre_hash = f"{timestamp}GET/api/v2/mix/position/single-position?{params_string}"

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

            response = requests.get(url, headers=headers, params=params)
            data = response.json()
            print(f"📖 Bitget Position Response: {data}", flush=True)

            if data.get("code") == "22002":
                return False

            positions = data.get("data", [])
            if isinstance(positions, list) and positions:
                return True

            return False

    except Exception as e:
        print(f"❌ Error checking position status: {e}", flush=True)
    return True

def send_bybit_order(symbol, side, qty):
    if SIMULATE_FAILURE:
        print("🚧 SIMULATE_FAILURE is ON. Simulating failed Bybit order execution.", flush=True)
        return 500, '{"msg": "Simulated failure"}'

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
    print(f"📤 Bybit API Response: {response.status_code} {response.text}", flush=True)
    return response.status_code, response.text

def send_bitget_order(symbol, side, qty):
    if SIMULATE_FAILURE:
        print("🚧 SIMULATE_FAILURE is ON. Simulating failed Bitget order execution.", flush=True)
        return 500, '{"msg": "Simulated failure"}'

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
    print(f"📤 Bitget API Response: {response.status_code} {response.text}", flush=True)
    return response.status_code, response.text

def close_position_with_retry(exchange, symbol, side, qty):
    attempt = 0

    while True:
        attempt += 1
        is_open = check_position_open(exchange, symbol)

        if not is_open:
            print(f"✅ Position already closed. Exiting retry loop at attempt #{attempt}", flush=True)
            return

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

        print(f"❌ API Response: Status={status_code}, Response={response}", flush=True)
        time.sleep(0.2)

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
