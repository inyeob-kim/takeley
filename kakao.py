import requests
import json
import os

def get_token_file_path(TOKENS_DIR, user_id):
    return os.path.join(TOKENS_DIR, f"{user_id}.json")

# 🔑 액세스 토큰 요청 (처음 1회만 필요)
def request_kakao_token(token_path, authorize_code):
    url = 'https://kauth.kakao.com/oauth/token'
    rest_api_key = 'b436bf7175bece1b93ec143a5e3b3f4c'
    redirect_uri = 'https://example.com/oauth'
    authorize_code = authorize_code  

    data = {
        'grant_type': 'authorization_code',
        'client_id': rest_api_key,
        'redirect_uri': redirect_uri,
        'code': authorize_code,
    }

    response = requests.post(url, data=data)
    tokens = response.json()

    # 응답 출력
    print("🔐 받은 토큰:", tokens)

    # 에러 체크
    if "access_token" not in tokens:
        print("❌ access_token 발급 실패:", tokens)
        return

    # JSON 파일로 저장
    with open(token_path, "w", encoding="utf-8") as fp:
        json.dump(tokens, fp, ensure_ascii=False, indent=2)
        print("✅ 토큰 저장 완료")


def get_kakao_friends_list(me_token_path):
    with open(me_token_path, "r", encoding="utf-8") as fp:
        tokens = json.load(fp)
    access_token = tokens["access_token"]

    url = "https://kapi.kakao.com/v1/api/talk/friends"
    headers = {
        "Authorization": f"Bearer {access_token}"
    }

    response = requests.get(url, headers=headers)
    result = response.json()
    print("👥 Friends List:", result)

    uuids = [friend["uuid"] for friend in result.get("elements", [])]

    return uuids

def send_kakao_messages(TOKENS_DIR, message):

        # Get Friend's UUID List
    friend_uuid_list = get_kakao_friends_list(get_token_file_path(TOKENS_DIR, "me"))

    user_list = ["me"] + friend_uuid_list

    for user in user_list:

        token_path = get_token_file_path(TOKENS_DIR, user)

        try:
            with open(token_path, "r", encoding="utf-8") as fp:
                tokens = json.load(fp)
            access_token = tokens["access_token"]
        except (FileNotFoundError, KeyError) as e:
            print(f"❌ [{user}] access_token 누락 또는 파일 없음. 먼저 request_kakao_token()을 실행하세요.")
            continue

        headers = {
            "Authorization": f"Bearer {access_token}"
        }

        if user == "me":
            url = "https://kapi.kakao.com/v2/api/talk/memo/default/send"
            data = {
                "template_object": json.dumps({
                    "object_type": "text",
                    "text": message,
                    "link": { 
                        "web_url": "https://twitter.com",
                        "mobile_web_url": "https://twitter.com"
                    },
                    "button_title": "트윗 보기"
                }, ensure_ascii=False)
            }
        else:
            # 친구에게 보내기
            url = "https://kapi.kakao.com/v1/api/talk/friends/message/default/send"
            # uuid는 사전에 확보되어 있어야 함 (예: get_kakao_friends_list 함수 활용)
            friend_uuid = user  # KAKAO_USER를 uuid 문자열로 가정
            data = {
                "receiver_uuids": json.dumps([friend_uuid]),
                "template_object": json.dumps({
                    "object_type": "text",
                    "text": message,
                    "link": {
                        "web_url": "https://twitter.com",
                        "mobile_web_url": "https://twitter.com"
                    },
                    "button_title": "트윗 보기"
                }, ensure_ascii=False)
            }

        response = requests.post(url, headers=headers, data=data)
        print(f"📨 [{user}] 응답 코드:", response.status_code)

        try:
            res_json = response.json()
            if res_json.get("result_code") == 0:
                print(f"📤 [{user}] KakaoTalk message sent successfully!")
            else:
                print(f"❌ [{user}] KakaoTalk message failed. Error:", res_json)
        except Exception as e:
            print(f"⚠️ [{user}] 응답 파싱 실패:", response.text)