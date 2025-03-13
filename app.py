from flask import Flask, request, jsonify
import requests

app = Flask(__name__)

def calculate_values(data):
    """Calculates Maximum Filling Ratio, Volume, and Mass."""
    density15 = data.get('density15')
    density50 = data.get('density50')
    tank_capacity = data.get('tankCapacity')

    if density15 is not None and tank_capacity is not None:
        max_permitted_mass = density15 * tank_capacity
        max_permitted_volume = tank_capacity
        max_filling_ratio = 1 #assumed 1, adjust as needed.
        return {
            "maxFillingRatio": max_filling_ratio,
            "maxPermittedVolume": max_permitted_volume,
            "maxPermittedMass": max_permitted_mass
        }
    else:
        return None

@app.route('/send-email', methods=['POST'])
def send_email():
    try:
        data = request.get_json()
        print("Received data:", data)

        # Basic Validation
        if not all(key in data for key in ['firstName', 'email']):
            return jsonify({"error": "Missing required fields"}), 400

        # Check for "Found" or "Not Found" (replace with your actual logic)
        calculated_values = calculate_values(data) #replace with your database or API call.
        if calculated_values:
            response_message = {
                "maxFillingRatio": calculated_values["maxFillingRatio"],
                "maxPermittedVolume": calculated_values["maxPermittedVolume"],
                "maxPermittedMass": calculated_values["maxPermittedMass"]
            }
        else:
            response_message = {
                "message": "The UN number or cargo name shared is likely not associated with a liquid cargo.\nHowever, Team BOLT will check and get back to you soon."
            }

        # Brevo Contact Creation/Update
        brevo_api_key = "YOUR_BREVO_API_KEY"
        brevo_contact_url = "YOUR_BREVO_CONTACT_ENDPOINT"

        headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "api-key": brevo_api_key
        }

        brevo_contact_response = requests.post(brevo_contact_url, headers=headers, json=data)
        print(f"Brevo contact response: {brevo_contact_response.json()}")

        if brevo_contact_response.status_code not in [200, 201]:
            print(f"Brevo contact error: {brevo_contact_response.json()}")
            return jsonify({"error": "Brevo contact API error", "details": brevo_contact_response.json()}), brevo_contact_response.status_code

        # Brevo Email Sending
        brevo_email_url = "YOUR_BREVO_EMAIL_ENDPOINT"
        email_data = {
            "sender": {"name": "BOLT", "email": "your_sender_email@example.com"},
            "to": [{"email": data["email"]}],
            "templateId": YOUR_EMAIL_TEMPLATE_ID,
            "params": {
                "cargoName": data.get("cargoInfo", "N/A"),
                "maxFillingRatio": response_message.get("maxFillingRatio", "N/A"),
                "maxPermittedVolume": response_message.get("maxPermittedVolume", "N/A"),
                "maxPermittedMass": response_message.get("maxPermittedMass", "N/A"),
                "message": response_message.get("message", "N/A"),
            }
        }
        brevo_email_response = requests.post(brevo_email_url, headers=headers, json=email_data)
        print(f"Brevo email response: {brevo_email_response.json()}")
        if brevo_email_response.status_code not in [200, 201]:
            print(f"brevo email error: {brevo_email_response.json()}")
            return jsonify({"error": "Brevo email API error", "details": brevo_email_response.json()}), brevo_email_response.status_code

        return jsonify(response_message), 200

    except Exception as e:
        print("Error:", e)
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
