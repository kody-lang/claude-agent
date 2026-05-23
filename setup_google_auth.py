"""Run this once to generate the Google OAuth token file.

Usage:
    python setup_google_auth.py

It will open a browser window for you to authorize the app.
The token is saved to the path set in GOOGLE_TOKEN_PATH (default: google_token.json).
"""
import os
from google_auth_oauthlib.flow import InstalledAppFlow
from dotenv import load_dotenv

load_dotenv()

SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/documents.readonly",
]

credentials_path = os.environ.get("GOOGLE_CREDENTIALS_PATH", "google_credentials.json")
token_path = os.environ.get("GOOGLE_TOKEN_PATH", "google_token.json")

flow = InstalledAppFlow.from_client_secrets_file(credentials_path, scopes=SCOPES)
creds = flow.run_local_server(port=0)

with open(token_path, "w") as f:
    f.write(creds.to_json())

print(f"Token saved → {token_path}")
