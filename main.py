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
BITGET_API_KEY = os.getenv("BITGET_API_KEY")
BITGET_API_SECRET = os.getenv("BITGET_API_SECRET")
BITGET_API_PASSPHRASE = os.getenv("BITGET_API_PASSPHRASE")

def get_timestamp():
    return str(int(time.time() * 1000))

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
    url_path = "/api/v2/mix/order/placeOrder"
    url = f"https://api.bitget.com{url_path}"
    timestamp = str(int(time.time() * 1000))

    body = {
        "symbol": symbol,
        "marginCoin": "USDT",
        "side": side.capitalize(),
        "orderType": "market",
        "size": qty,
        "reduceOnly": True,
        "productType": "USDT-FUTURES"
    }

    body_json = json.dumps(body, separators=(',', ':'))
    pre_hash = f"{timestamp}POST{url_path}{body_json}"

    signature = hmac.new(
        bytes(BITGET_API_SECRET, "utf-8"),
        pre_hash.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()

    headers = {
        "ACCESS-KEY": BITGET_API_KEY,
        "ACCESS-SIGN": signature,
        "ACCESS-TIMESTAMP": timestamp,
        "ACCESS-PASSPHRASE": BITGET_API_PASSPHRASE,
        "Content-Type": "application/json"
    }

    print("📦 Final Bitget request body:", body_json, flush=True)
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

    if not data:
        return jsonify({"message": "No data received"}), 400

    if data.get("key") != WEBHOOK_KEY:
        print("[X] Wrong key",
