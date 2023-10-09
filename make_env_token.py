import json
import os

from dotenv import load_dotenv
from google_auth_oauthlib.flow import InstalledAppFlow

GOOGLE_AUTH_REDIRECT_URI = "https://127.0.0.1/"

load_dotenv()
google_client_secrets = json.loads(os.getenv("GOOGLE_APPLICATION_CREDENTIALS"))
discord_bot_token = os.getenv('DISCORD_TOKEN')

flow = InstalledAppFlow.from_client_config(
    google_client_secrets,
    scopes=['https://www.googleapis.com/auth/admin.directory.group.readonly'],
    redirect_uri=GOOGLE_AUTH_REDIRECT_URI)
print(flow.authorization_url())
url = input().strip()
print(url)
flow.fetch_token(authorization_response=url)
credentials = flow.credentials
print(credentials.to_json())
open("creds.json", "w+").write(credentials.to_json().replace("\"", "\\\""))
