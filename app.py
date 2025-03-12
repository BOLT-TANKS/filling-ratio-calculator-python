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

def find_best_match(cargo_info, df):
    """Finds the best matching row in the DataFrame."""
    best_match = None
    best_score = 0

    for index, row in df.iterrows():
        un_no = str(row["UN No."]).lower()  # Convert to string and lowercase
        cargo_name = str(row["Cargo Name"]).lower() #Convert to string and lowercase
        search_term = cargo_info.lower() #Convert to lowercase

        un_score = fuzz.ratio(search_term, un_no)
        cargo_score = fuzz.ratio(search_term, cargo_name)
        score = max(un_score, cargo_score) #Use the best score of the two.

        if score > 70:  # Adjust threshold as needed
            best_score = score
            best_match = row

    if best_score > 70:  # Adjust threshold as needed
        return best_match
    else:
        return None

def get_tp_code(cargo_info):
    """Reads the Excel sheet and returns the TP Code."""
    try:
        df = pd.read_excel(EXCEL_FILE)
        best_match = find_best_match(cargo_info, df)

        if best_match is not None:
            return best_match["TP Code"]
        else:
            return None
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
            return jsonify({"success": False, "message": "TP Code not found for the given UN number or cargo name."}), 400

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
            "params": data,
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
        print("Error:", e)
        return jsonify({"success": False, "message": "Error processing request."}), 500

if __name__ == "__main__":
    app.run(debug=False)
