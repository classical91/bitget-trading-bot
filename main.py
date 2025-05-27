from flask import Flask, request, jsonify
import requests, hmac, hashlib, time, json, os

app = Flask(__name__)

# Load Bitget credentials from environment variables
API_KEY = os.getenv("BITGET_API_KEY")
API_SECRET = os.getenv("BITGET_API_SECRET")
PASSPHRASE = os.getenv("BITGET_PASSPHRASE")

def generate_signature(timestamp, method, request_path, body=""):
    message = f"{timestamp}{method}{request_path}{body}"
    return hmac.new(API_SECRET.encode(), message.encode(), hashlib.sha256).hexdigest()

def place_order(action, symbol, amount):
    url = "/api/v1/spot/order"
    full_url = f"https://api.bitget.com{url}"
    timestamp = str(int(time.time() * 1000))
    method = "POST"
    
    order = {
        "symbol": symbol,
        "side": action,
        "type": "market",
        "size": str(amount)
    }

    body = json.dumps(order, separators=(',', ':'))
    signature = generate_signature(timestamp, method, url, body)

    headers = {
        "Content-Type": "application/json",
        "ACCESS-KEY": API_KEY,
        "ACCESS-SIGN": signature,
        "ACCESS-TIMESTAMP": timestamp,
        "ACCESS-PASSPHRASE": PASSPHRASE
    }

    response = requests.post(full_url, headers=headers, data=body)
    return response.json()

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        data = request.json
        print("Webhook Received:", data)

        required_keys = {"action", "symbol", "amount"}
        if not required_keys.issubset(data):
            return jsonify({"error": "Missing required keys in webhook payload"}), 400

        result = place_order(data["action"], data["symbol"], data["amount"])
        return jsonify(result)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        data = request.json
        print("Webhook Received:", data)
        print("API_KEY:", API_KEY)  # Debug print
        result = place_order(data["action"], data["symbol"], data["amount"])
        return jsonify(result)
    except Exception as e:
        print("Webhook Error:", str(e))
        return jsonify({"error": str(e)}), 500