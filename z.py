import os,json, requests

# Load the environment variables from the .env file (For local enviroment)
from dotenv import load_dotenv
load_dotenv()

# Load Driver's Configuration
MEETJOHNNY_API_ENDPOINT = os.getenv('MEETJOHNNY_API_ENDPOINT')

# Send Post Request to the MeetJohnny website API
def send_data():
    with open('data/data.json', 'r') as file:
        data = json.load(file)

    url = MEETJOHNNY_API_ENDPOINT  # Replace with your actual endpoint
    headers = {'Content-Type': 'application/json'}

    try:
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()  # Raise an exception for HTTP errors
        print(f"System: Successfully sent POST request. Response: {response.text}")
    except requests.exceptions.RequestException as e:
        print(f"System: Failed to send POST request. Error: {e}")

send_data()