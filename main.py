"""main.py – Production-ready Bitget webhook handler
--------------------------------------------------
Receives TradingView/any JSON webhook in the format
   {"action": "open_long", "symbol": "BTCUSDT", "amount": 0.001}
Maps the action to Bitget USDT‑M Futures side + positionAction
Signs and submits a *market* order to Bitget’s unified‑contracts (mix) API
Logs the full Bitget API response so you always know what happened
"""
from __future__ import annotations

import json
import os
import time
import hmac
import hashlib
import base64
import traceback

import requests
from flask import Flask, request

app = Flask(__name__)

# ---------------------------------------------------------------------------
# Bitget credentials pulled from env
# ---------------------------------------------------------------------------
API_KEY: str | None = os.getenv("BITGET_API_KEY")
API_SECRET: str | None = os.getenv("BITGET_API_SECRET")
API_PASSPHRASE: str | None = os.getenv("BITGET_API_PASSPHRASE")
SUB_UID: str | None = os.getenv("BITGET_SUBACCOUNT_UID")  # optional

if not all([API_KEY, API_SECRET, API_PASSPHRASE]):
    print("⚠️  Bitget API environment variables are missing — orders will fail!")

BITGET_BASE = "https://api.bitget.com"
ORDER_ENDPOINT = "/api/mix/v1/order/placeOrder"

# ---------------------------------------------------------------------------
# CONFIG: Set to True if your Bitget account is in Hedge Mode (dual positions)
# ---------------------------------------------------------------------------
IS_HEDGE_MODE = True  # <-- CHANGE to True if you use Hedge Mode in Bitget

# ---------------------------------------------------------------------------
# Utility: sign request
# ---------------------------------------------------------------------------
def _bitget_sign(timestamp: str, method: str, path: str, body: str) -> str:
    prehash = f"{timestamp}{method}{path}{body}"
    digest = hmac.new(API_SECRET.encode(), prehash.encode(), hashlib.sha256).digest()
    return base64.b64encode(digest).decode()

# ---------------------------------------------------------------------------
# Translate TradingView action -> Bitget side/position
# ---------------------------------------------------------------------------
ACTION_MAP = {
    "open_long":  {"side": "buy",  "posSide": "long"},
    "close_long": {"side": "sell", "posSide": "long"},
    "open_short": {"side": "sell", "posSide": "short"},
    "close_short":{"side": "buy",  "posSide": "short"},
}

# ---------------------------------------------------------------------------
# Core order function
# ---------------------------------------------------------------------------
def place_order(action: str, symbol: str, amount: float):
    """Submit a market order to Bitget and return the JSON response."""
    try:
        if action not in ACTION_MAP:
            raise ValueError(f"Unsupported action '{action}'. Must be one of: {list(ACTION_MAP)}")

        side_info = ACTION_MAP[action]
        payload = {
            "symbol": symbol,          # e.g. BTCUSDT
            "marginCoin": "USDT",      # USDT‑M contracts
            "size": str(amount),       # string per API spec
            "side": side_info["side"],
            "orderType": "market",
        }
        if IS_HEDGE_MODE:
            payload["posSide"] = side_info["posSide"]
        if SUB_UID:
            payload["subUid"] = SUB_UID

        body = json.dumps(payload, separators=(",", ":"))
        ts = str(int(time.time() * 1000))
        signature = _bitget_sign(ts, "POST", ORDER_ENDPOINT, body)

        headers = {
            "ACCESS-KEY": API_KEY,
            "ACCESS-SIGN": signature,
            "ACCESS-TIMESTAMP": ts,
            "ACCESS-PASSPHRASE": API_PASSPHRASE,
            "Content-Type": "application/json",
        }

        print("Submitting to Bitget →", payload)
        resp = requests.post(BITGET_BASE + ORDER_ENDPOINT, headers=headers, data=body, timeout=10)
        print("Bitget response status:", resp.status_code)
        print("Bitget response text:", resp.text)
        return resp.json() if resp.headers.get("Content-Type", "").startswith("application/json") else {"raw": resp.text}

    except Exception as err:
        print("❌ Error in place_order:", err)
        traceback.print_exc()
        return {"error": str(err)}

# ---------------------------------------------------------------------------
# Flask webhook route (RECOMMENDED VERSION)
# ---------------------------------------------------------------------------
from flask import jsonify  # Make sure this is imported!

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.json
    print(f"Webhook received: {data}")

    # Extract action, symbol, amount from webhook payload
    action = data.get('action')
    symbol = data.get('symbol')
    amount = data.get('amount')

    # Call the actual Bitget order function
    response = place_order(action, symbol, amount)

    print(f"Bitget API response: {response}")
    return jsonify({'result': response})

# ---------------------------------------------------------------------------
# Ping route (optional)
# ---------------------------------------------------------------------------
@app.route("/", methods=["GET"])
def index():
    return "Bitget trading bot is up!", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 8080)))

import sys, traceback

def _dump_startup_errors():
    try:
        yield
    except Exception:
        print("\n🔥  Fatal startup exception:\n")
        traceback.print_exc()
        sys.exit(1)

with _dump_startup_errors():
    pass  # the rest of the file is already executed, this just wraps it

