import requests
import json
import os

# Constants
TOKEN_FILE = "kakao_token.json"
REST_API_KEY = "411503d9d9ee7b73d3b46fdbb75a3911"
REDIRECT_URI = "https://example.com/oauth"
AUTH_CODE = "XGW7JoXqIxMR5l2TuwlK6fVcwxNYSKBHasqvtZhlzwIjQ5IDXtjTgwAAAAQKDRmQAAABlhm9dr-SBpCp5rpDbg"


def save_tokens(tokens):
    os.makedirs(os.path.dirname(TOKEN_FILE), exist_ok=True)
    with open(TOKEN_FILE, "w") as fp:
        json.dump(tokens, fp, indent=4)


def load_tokens():
    with open(TOKEN_FILE, "r") as fp:
        return json.load(fp)


def request_access_token():
    url = "https://kauth.kakao.com/oauth/token"
    data = {
        "grant_type": "authorization_code",
        "client_id": REST_API_KEY,
        "redirect_uri": REDIRECT_URI,
        "code": AUTH_CODE,
    }

    response = requests.post(url, data=data)
    if response.status_code == 200:
        tokens = response.json()
        save_tokens(tokens)
        print("✅ Access token successfully obtained and saved.")
    else:
        print(f"❌ Failed to get token. Status code: {response.status_code}, Error: {response.text}")


def ensure_token():
    if os.path.exists(TOKEN_FILE):
        print("🔑 Access token already exists.")
    else:
        print("🔄 Access token not found. Requesting a new one...")
        request_access_token()


def send_kakao_message(message="Hello, world!"):
    ensure_token()

    try:
        tokens = load_tokens()
    except Exception as e:
        print(f"❌ Error loading token: {e}")
        return

    url = "https://kapi.kakao.com/v2/api/talk/memo/default/send"
    headers = {
        "Authorization": "Bearer " + tokens["access_token"]
    }

    template = {
        "object_type": "text",
        "text": message,
        "link": {
            "web_url": "https://www.naver.com"
        }
    }

    data = {
        "template_object": json.dumps(template)
    }

    response = requests.post(url, headers=headers, data=data)

    try:
        result = response.json()
    except json.JSONDecodeError:
        print(f"❌ Failed to decode JSON response: {response.text}")
        return

    if response.status_code == 200 and result.get("result_code") == 0:
        print("✅ 메시지를 성공적으로 보냈습니다.")
    else:
        print(f"❌ 메시지를 보내지 못했습니다. 오류: {result}")


# Example usage:
# send_kakao_message("카카오 메시지 테스트입니다!")
