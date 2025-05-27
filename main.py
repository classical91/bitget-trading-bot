from flask import Flask, request, jsonify
import traceback

app = Flask(__name__)

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        data = request.json
        print("Webhook Received:", data)

        # Debug logs
        print("Action:", data.get("action"))
        print("Symbol:", data.get("symbol"))
        print("Amount:", data.get("amount"))
        print("Using API_KEY:", API_KEY)

        result = place_order(data["action"], data["symbol"], data["amount"])
        print("Order Result:", result)
        return jsonify(result)
    except Exception as e:
        print("Webhook Error:", str(e))
        traceback.print_exc()  # This prints the full error stack
        return jsonify({"error": str(e)}), 500
