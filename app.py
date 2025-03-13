from flask import Flask, request, jsonify
import requests
import os
import pandas as pd
from flask_cors import CORS
from fuzzywuzzy import fuzz

app = Flask(__name__)
CORS(app, origins="https://www.bolt-tanks.com")

BREVO_API_KEY = os.environ.get("BREVO_API_KEY")
TEMPLATE_ID = int(os.environ.get("TEMPLATE_ID"))
EXCEL_FILE = "cargo_data.xlsx"

def get_tp_code(cargo_info):
    """Reads the Excel sheet and returns the TP Code."""
    try:
        df = pd.read_excel(EXCEL_FILE)
        cargo_info_lower = cargo_info.lower()

        for index, row in df.iterrows():
            un_no = str(row["UN No."]).lower()
            cargo_name = str(row["Cargo Name"]).lower()

            if cargo_info_lower == un_no or cargo_info_lower == cargo_name:
                tp_code = row["TP Code"]
                if pd.isna(tp_code) or not isinstance(tp_code, str) or tp_code.strip() == "":
                    return "INVALID_TP_CODE"
                return tp_code

        return None  # No exact match found

    except FileNotFoundError:
        return None

@app.route("/send-email", methods=["POST"])
def send_email():
    data = request.get_json()
    print("Received data:", data)

    try:
        density15 = float(data.get("density15"))
        density50 = float(data.get("density50"))
        tankCapacity = float(data.get("tankCapacity"))
        cargo_info = data.get("cargoInfo")

        tpCode = get_tp_code(cargo_info)
        if tpCode is None:
            error_message = "The UN number or cargo name shared is likely not associated with a liquid cargo.      However, BOLT team will get back to you for assistance."
            return jsonify({"success": False, "message": error_message}), 400
        elif tpCode == "INVALID_TP_CODE":
            error_message = "The UN number or cargo name shared is likely not associated with a liquid cargo.      However, BOLT team will get back to you for assistance."
            return jsonify({"success": False, "message": error_message}), 400

        alpha = (density15 - density50) / (density50 * 35)
        if tpCode == "TP1":
            max_filling_percentage = 97 / (1 + alpha * (50 - 15))
        elif tpCode == "TP2":
            max_filling_percentage = 95 / (1 + alpha * (50 - 15))
        else:
            return jsonify({"success": False, "message": "Invalid TP Code from Excel."}), 400

        max_volume = (tankCapacity * max_filling_percentage) / 100
        max_mass = max_volume * density15

        brevo_headers = {
            "accept": "application/json",
            "api-key": BREVO_API_KEY,
            "content-type": "application/json",
        }

        contact_url = f"https://api.brevo.com/v3/contacts/{data.get('email')}"
        contact_response = requests.get(contact_url, headers=brevo_headers)

        if contact_response.status_code == 200:
            requests.put(contact_url, headers=brevo_headers, json={"attributes": data})
            print("Existing contact updated")
        else:
            requests.post("https://api.brevo.com/v3/contacts", headers=brevo_headers, json={"email": data.get("email"), "attributes": data})
            print("New contact created")

        email_data = {
            "to": [{"email": data.get("email")}],
            "templateId": TEMPLATE_ID,
            "params": {**data, "error_message": error_message if 'error_message' in locals() else None},
        }
        requests.post("https://api.brevo.com/v3/smtp/email", headers=brevo_headers, json=email_data)

        return jsonify({
            "success": True,
            "message": "Email sent and contact saved/updated.",
            "maxFillingPercentage": max_filling_percentage,
            "maxVolume": max_volume,
            "maxMass": max_mass,
        })

    except Exception as e:
        import traceback
        print("Error:", e)
        print(traceback.format_exc())
        return jsonify({"success": False, "message": "Error processing request."}), 500

if __name__ == "__main__":
    app.run(debug=False)
