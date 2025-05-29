"""main.py – Production‑ready Bitget webhook handler
--------------------------------------------------
Receives TradingView/any JSON webhook in the format
   {"action": "open_long", "symbol": "BTCUSDT", "amount": 0.001}
Maps the action to Bitget USDT‑M Futures side + tradeSide (v2 Hedge‑mode API)
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
from flask import Flask, request, jsonify

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
# CONFIG: your Bitget account must be in Hedge Mode for the mapping below
# ---------------------------------------------------------------------------
IS_HEDGE_MODE = True  # set to False and remove tradeSide if you use One‑way mode

# ---------------------------------------------------------------------------
# Utility: sign request
# ---------------------------------------------------------------------------

def _bitget_sign(timestamp: str, method: str, path: str, body: str) -> str:
    prehash = f"{timestamp}{method}{path}{body}"
    digest = hmac.new(API_SECRET.encode(), prehash.encode(), hashlib.sha256).digest()
    return base64.b64encode(digest).decode()

# ---------------------------------------------------------------------------
# Translate TradingView action ➟ Bitget side + tradeSide (v2 API)
# ---------------------------------------------------------------------------
ACTION_MAP = {
    "open_long":  {"side": "buy",  "tradeSide": "open"},
    "close_long": {"side": "buy",  "tradeSide": "close"},
    "open_short": {"side": "sell", "tradeSide": "open"},
    "close_short":{"side": "sell", "tradeSide": "close"},
}

# ---------------------------------------------------------------------------
# Core order function
# ---------------------------------------------------------------------------

def place_order_raw(payload: dict):
    """Send the raw JSON payload to Bitget and return its response as dict."""
    try:
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
        if resp.headers.get("Content-Type", "").startswith("application/json"):
            return resp.json()
        return {"raw": resp.text}
    except Exception as err:
        print("❌ Error in place_order_raw:", err)
        traceback.print_exc()
        return {"error": str(err)}


# ---------------------------------------------------------------------------
# Flask webhook route
# ---------------------------------------------------------------------------

@app.route('/webhook', methods=['POST'])
def webhook():
    """Receive TradingView/any JSON, map, and place Bitget order."""
    try:
        data = request.get_json(force=True, silent=True)
        if data is None:
            data = request.data.decode('utf-8')
            print("Webhook data as text:", data)
            return 'bad request', 400
        print(f"Webhook Received: {data}")

        # minimal TradingView payload: action/symbol/amount
        action  = data.get("action")
        symbol  = data.get("symbol")
        amount  = data.get("amount")

        if not action or not symbol or amount is None:
            return jsonify({"error": "Missing action, symbol, or amount"}), 400
        if action not in ACTION_MAP:
            return jsonify({"error": f"Unknown action '{action}'"}), 400

        payload = {
            "symbol":      symbol,
            "marginCoin":  "USDT",
            "size":        str(amount),   # measured in base‑asset contracts (BTC, ETH…)
            "side":        ACTION_MAP[action]["side"],
            "tradeSide":   ACTION_MAP[action]["tradeSide"],
            "orderType":   "market",
        }

        response = place_order_raw(payload)
        print("Order response:", response)
        return jsonify(response), 200

    except Exception as e:
        print(f"Error: {e}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 400


# ---------------------------------------------------------------------------
# Ping route (optional)
# ---------------------------------------------------------------------------

@app.route("/", methods=["GET"])
def index():
    return "Bitget trading bot is up!", 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 8080)))
