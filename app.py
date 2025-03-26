from flask import Flask, request, jsonify
import requests
import os
import pandas as pd
from flask_cors import CORS

app = Flask(__name__)
CORS(app, origins="https://www.bolt-tanks.com")

BREVO_API_KEY = os.environ.get("BREVO_API_KEY")
TEMPLATE_ID = int(os.environ.get("TEMPLATE_ID"))

try:
    df = pd.read_excel("cargo_data.xlsx")
    df["UN No."] = df["UN No."].astype(str).str.strip().str.lower() #Convert to lowercase
    df["Cargo Name"] = df["Cargo Name"].astype(str).str.strip().str.lower() #Convert to lowercase
except Exception as e:
    print(f"Error loading Excel: {e}")
    df = pd.DataFrame()

@app.route("/send-email", methods=["POST"])
def send_email():
    data = request.get_json()
    print("Received data:", data)

    try:
        density15 = float(data.get("density15"))
        density50 = float(data.get("density50"))
        tankCapacity = float(data.get("tankCapacity"))
        un_number = str(data.get("unNumber")).strip().lower() #Convert to lowercase
        cargo_name = str(data.get("cargoName")).strip().lower() #Convert to lowercase

        print(f"UN Number from request: '{un_number}'")
        print(f"Cargo Name from request: '{cargo_name}'")

        if df.empty:
            return jsonify({
                "success": False,
                "message": "Database unavailable: Unable to verify UN number and Cargo Name. Please try again later."
            }), 500

        if un_number not in df['UN No.'].values or cargo_name not in df['Cargo Name'].values:
            return jsonify({
                "success": False,
                "message": "Verification Failed: The provided UN number or Cargo Name is not associated with a liquid cargo. Our team will review and get back to you."
            }), 404

        matching_rows = df[(df["UN No."] == un_number) & (df["Cargo Name"] == cargo_name)]

        if matching_rows.empty:
            return jsonify({
                "success": False,
                "message": "Mismatch Detected: The provided UN Number and Cargo Name do not correspond. Please check and provide accurate details."
            }), 400

        # ... (rest of your code)

    except Exception as e:
        print("Error:", e)
        return jsonify({"success": False, "message": "Processing error. Please try again later."}), 500

if __name__ == "__main__":
    app.run(debug=False)
