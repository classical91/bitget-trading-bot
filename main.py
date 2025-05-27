"""main.py – Production‑ready Bitget webhook handler
--------------------------------------------------
✅ Receives TradingView/any JSON webhook in the format
   {"action": "open_long", "symbol": "BTCUSDT", "amount": 0.001}
✅ Maps the action to Bitget USDT‑M Futures side + positionAction
✅ Signs and submits a *market* order to Bitget’s unified‑contracts (mix) API
✅ Logs the full Bitget API response so you always know what happened

Environment variables required in Railway (‑> *Variables* tab):
    BITGET_API_KEY          – your Bitget API key
    BITGET_API_SECRET       – your API secret
    BITGET_API_PASSPHRASE   – the passphrase you set when creating the key
    BITGET_SUBACCOUNT_UID   – optional, only if you trade from a sub‑UID

Install deps (already in requirements.txt): Flask, requests.
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
# Bitget credentials pulled from env (never hard‑code sensitive info!)
# ---------------------------------------------------------------------------
API_KEY: str | None = os.getenv("BITGET_API_KEY")
API_SECRET: str | None = os.getenv("BITGET_API_SECRET")
API_PASSPHRASE: str | None = os.getenv("BITGET_API_PASSPHRASE")
SUB_UID: str | None = os.getenv("BITGET_SUBACCOUNT_UID")  # optional

if not all([API_KEY, API_SECRET, API_PASSPHRASE]):
    print("⚠️  Bitget API environment variables are missing — orders will fail!")

BITGET_BASE = "https://api.bitget.com"
ORDER_ENDPOINT = "/api/mix/v1/order/placeOrder"  # USDT‑M futures/linear contracts

# ---------------------------------------------------------------------------
# Utility: sign request ------------------------------------------------------
# ---------------------------------------------------------------------------

def _bitget_sign(timestamp: str, method: str, path: str, body: str) -> str:
    """Return base64‑encoded HMAC‑SHA256 signature."""
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
# Core order function --------------------------------------------------------
# ---------------------------------------------------------------------------

def place_order(action: str, symbol: str, amount: float):
    """Submit a market order to Bitget and return the JSON response."""
    try:
        if action not in ACTION_MAP:
            raise ValueError(f"Unsupported action '{action}'. Must be one of: {list(ACTION_MAP)}")

        side_info = ACTION_MAP[action]
        payload = {
            "symbol": symbol,          # e.g. BTCUSDT
            "marginCoin": "USDT",    # USDT‑M contracts
            "size": str(amount),      # string per API spec
            "side": side_info["side"],
            "orderType": "market",
            "posSide": side_info["posSide"],
        }
        if SUB_UID:
            payload["subUid"] = SUB_UID

        body = json.dumps(payload, separators=(",", ":"))  # compact JSON
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
# Flask webhook route -------------------------------------------------------
# ---------------------------------------------------------------------------

@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.get_json(force=True)
        print("Webhook Received:", data)

        # Basic validation -----------------------------------------------
        required = {"action", "symbol", "amount"}
        if not required.issubset(data):
            return jsonify({"error": f"Missing fields — required {required}"}), 400

        result = place_order(str(data["action"]).lower(), data["symbol"], float(data["amount"]))
        print("Order Result:", result)
        return jsonify(result)

    except Exception as e:
        print("Webhook Error:", e)
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

# ---------------------------------------------------------------------------
# Ping route (optional) -----------------------------------------------------
# ---------------------------------------------------------------------------
@app.route("/", methods=["GET"])
def index():
    return "Bitget trading bot is up!", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 8080)))
