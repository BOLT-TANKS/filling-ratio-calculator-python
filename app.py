from flask import Flask, request, jsonify
import requests
import os
import pandas as pd
from flask_cors import CORS
import logging

app = Flask(__name__)  # Create the Flask app instance here!
CORS(app, origins="https://www.bolt-tanks.com")

BREVO_API_KEY = os.environ.get("BREVO_API_KEY")
TEMPLATE_ID = int(os.environ.get("TEMPLATE_ID"))

# Configure logging
logging.basicConfig(level=logging.ERROR)

try:
    df = pd.read_excel("cargo_data.xlsx")
    df["UN No."] = df["UN No."].astype(str).str.strip().str.lower()
    df["Cargo Name"] = df["Cargo Name"].astype(str).str.strip().str.lower()
except Exception as e:
    logging.error(f"Error loading Excel: {e}")
    df = pd.DataFrame()

@app.route("/send-email", methods=["POST"])
def send_email():
    # ... (rest of your send_email function code)
    data = request.get_json()
    logging.debug(f"Received data: {data}")

    try:
        density15 = float(data.get("density15"))
        density50 = float(data.get("density50"))
        tankCapacity = float(data.get("tankCapacity"))
        un_number = str(data.get("unNumber")).strip().lower()
        cargo_name = str(data.get("cargoName")).strip().lower()

        logging.debug(f"UN Number from request: '{un_number}'")
        logging.debug(f"Cargo Name from request: '{cargo_name}'")

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

        tp_code = matching_rows.iloc[0]["TP Code"]
        logging.debug(f"TP Code found: {tp_code}")

        alpha = (density15 - density50) / (density50 * 35)
        if tp_code == "TP1":
            max_filling_percentage = 97 / (1 + alpha * (50 - 15))
        elif tp_code == "TP2":
            max_filling_percentage = 95 / (1 + alpha * (50 - 15))
        else:
            return jsonify({
                "success": False,
                "message": "Invalid data: TP Code not recognized."
            }), 500

        max_volume = (tankCapacity * max_filling_percentage) / 100
        max_mass = max_volume * density15

        brevo_headers = {
            "accept": "application/json",
            "api-key": BREVO_API_KEY,
            "content-type": "application/json",
        }

        try:
            contact_url = f"https://api.brevo.com/v3/contacts/{data.get('email')}"
            contact_response = requests.get(contact_url, headers=brevo_headers)

            if contact_response.status_code == 200:
                requests.put(contact_url, headers=brevo_headers, json={"attributes": data})
                logging.debug("Existing contact updated")
            else:
                requests.post("https://api.brevo.com/v3/contacts", headers=brevo_headers, json={"email": data.get("email"), "attributes": data})
                logging.debug("New contact created")

            email_data = {
                "to": [{"email": data.get("email")}],
                "templateId": TEMPLATE_ID,
                "params": {
                    **data,
                    "maxFillingPercentage": max_filling_percentage,
                    "maxVolume": max_volume,
                    "maxMass": max_mass,
                }
            }
            requests.post("https://api.brevo.com/v3/smtp/email", headers=brevo_headers, json=email_data)

            return jsonify({
                "success": True,
                "message": "Email sent successfully and contact information updated.",
                "maxFillingPercentage": max_filling_percentage,
                "maxVolume": max_volume,
                "maxMass": max_mass,
            })

        except requests.exceptions.RequestException as brevo_error:
            logging.error(f"Brevo API error: {brevo_error}")
            return jsonify({
                "success": False,
                "message": f"Brevo API error: {brevo_error}"
            }), 500

    except Exception as e:
        logging.error(f"Error: {e}")
        return jsonify({"success": False, "message": "Processing error. Please try again later."}), 500

if __name__ == "__main__":
    app.run(debug=False)
