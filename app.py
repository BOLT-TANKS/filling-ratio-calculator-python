from flask import Flask, request, jsonify
import requests
import os
from flask_cors import CORS
import pandas as pd

app = Flask(__name__)
CORS(app, origins="https://www.bolt-tanks.com")

BREVO_API_KEY = os.environ.get("BREVO_API_KEY")
TEMPLATE_ID = int(os.environ.get("TEMPLATE_ID"))

# Load Excel sheet
try:
    df = pd.read_excel("cargo_data.xlsx")
except FileNotFoundError:
    print("Error: Excel file cargo_data.xlsx not found.")
    df = None

@app.route("/send-email", methods=["POST"])
def send_email():
    data = request.get_json()
    print("Received data:", data)

    try:
        un_or_cargo = data.get("cargoInfo").lower() if data.get("cargoInfo") else "" #convert to lower, and handle none.

        if df is not None:
            # Search for TP code in Excel (case-insensitive)
            found_row = df[df["UN No."].str.lower() == un_or_cargo]
            if found_row.empty:
                found_row = df[df["Cargo Name"].str.lower() == un_or_cargo]

            if not found_row.empty:
                tp_code = found_row.iloc[0]["TP Code"]

                # Filling Ratio Calculation
                density15 = float(data.get("density15"))
                density50 = float(data.get("density50"))
                tankCapacity = float(data.get("tankCapacity"))

                alpha = (density15 - density50) / (density50 * 35)
                if tp_code == "TP1":
                    max_filling_percentage = 97 / (1 + alpha * (50 - 15))
                elif tp_code == "TP2":
                    max_filling_percentage = 95 / (1 + alpha * (50 - 15))
                else:
                    return jsonify({"success": False, "message": "Invalid TP Code."}), 400

                max_volume = (tankCapacity * max_filling_percentage) / 100
                max_mass = max_volume * density15

                response_message = {
                    "success": True,
                    "message": "Email sent and contact saved/updated.",
                    "maximum_filling_percentage": max_filling_percentage,
                    "maximum_permitted_volume": max_volume,
                    "maximum_permitted_mass": max_mass,
                    "cargo_name": data.get("cargoInfo")
                }
            else:
                response_message = {
                    "success": True,
                    "message": "The UN number or cargo name shared is likely not associated with a liquid cargo.\nHowever, Team BOLT will check and get back to you soon.",
                    "cargo_name": data.get("cargoInfo")
                }
        else:
            response_message = {
                "success": True,
                "message": "The UN number or cargo name shared is likely not associated with a liquid cargo.\nHowever, Team BOLT will check and get back to you soon.",
                "cargo_name": data.get("cargoInfo")
            }

        # Brevo Integration (Contact Creation/Update and Email Sending)
        brevo_headers = {
            "accept": "application/json",
            "api-key": BREVO_API_KEY,
            "content-type": "application/json",
        }

        # Check if contact exists
        contact_url = f"https://api.brevo.com/v3/contacts/{data.get('email')}"
        contact_response = requests.get(contact_url, headers=brevo_headers)

        if contact_response.status_code == 200:
            # Update existing contact
            requests.put(contact_url, headers=brevo_headers, json={"attributes": data})
            print("Existing contact updated")
        else:
            # Create new contact
            requests.post("https://api.brevo.com/v3/contacts", headers=brevo_headers, json={"email": data.get("email"), "attributes": data})
            print("New contact created")

        # Send email
        email_data = {
            "to": [{"email": data.get("email")}],
            "templateId": TEMPLATE_ID,
            "params": {
                "cargo_name": data.get("cargoInfo"),
                "maximum_filling_percentage": response_message.get("maximum_filling_percentage"),
                "maximum_permitted_volume": response_message.get("maximum_permitted_volume"),
                "maximum_permitted_mass": response_message.get("maximum_permitted_mass"),
                "message": response_message.get("message")
            },
        }
        requests.post("https://api.brevo.com/v3/smtp/email", headers=brevo_headers, json=email_data)

        return jsonify(response_message)

    except Exception as e:
        print("Error:", e)
        return jsonify({"success": False, "message": "Error processing request."}), 500

if __name__ == "__main__":
    app.run(debug=False)
