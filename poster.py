import os
import re
import time
from pathlib import Path
from typing import Tuple

import requests
import tweepy


HIGH_IMPACT_KEYWORDS = (
    "fed",
    "cpi",
    "tesla",
    "nvidia",
    "earnings",
    "war",
    "rate hike",
)


def should_generate_image(source_text: str) -> bool:
    text = (source_text or "").lower()
    return any(keyword in text for keyword in HIGH_IMPACT_KEYWORDS)


def build_imagefx_prompt_from_tweet(source_text: str) -> str:
    text = re.sub(r"https?://\S+", "", source_text)
    text = re.sub(r"[@#]\w+", "", text)
    text = re.sub(r"\s{2,}", " ", text).strip()
    return text


def generate_image_fx(prompt: str, out_path: str, size: str = "1600x900") -> str:
    imagefx_url = os.getenv("IMAGEFX_URL")
    imagefx_key = os.getenv("IMAGEFX_API_KEY")
    if not imagefx_url or not imagefx_key:
        raise RuntimeError("IMAGEFX_URL/IMAGEFX_API_KEY is not set")

    headers = {
        "Authorization": f"Bearer {imagefx_key}",
        "Content-Type": "application/json",
    }
    payload = {"prompt": prompt, "size": size, "n": 1}
    response = requests.post(imagefx_url, headers=headers, json=payload, timeout=120)
    response.raise_for_status()

    content_type = response.headers.get("content-type", "")
    out_path = str(Path(out_path))

    if content_type.startswith("image/"):
        with open(out_path, "wb") as f:
            f.write(response.content)
        return out_path

    data = response.json()
    image_url = data["data"][0]["url"]
    image_response = requests.get(image_url, timeout=120)
    image_response.raise_for_status()
    with open(out_path, "wb") as f:
        f.write(image_response.content)
    return out_path


def post_to_twitter(client_twitter: tweepy.Client, text: str, max_retries: int = 3) -> bool:
    for attempt in range(max_retries):
        try:
            client_twitter.create_tweet(text=text)
            print(f"[POST] success mode=text attempt={attempt + 1}")
            return True
        except Exception as e:
            print(f"[POST] failed mode=text retry={attempt + 1}/{max_retries} error={e}")
            time.sleep(5)
    return False


def post_to_twitter_with_image(
    client_twitter: tweepy.Client,
    api_v1: tweepy.API,
    text: str,
    image_path: str,
    alt_text: str | None = None,
    max_retries: int = 3,
) -> bool:
    for attempt in range(max_retries):
        try:
            media = api_v1.media_upload(filename=image_path)
            media_id = media.media_id_string
            if alt_text:
                api_v1.create_media_metadata(media_id, alt_text)
            client_twitter.create_tweet(text=text, media_ids=[media_id])
            print(f"[POST] success mode=image attempt={attempt + 1}")
            return True
        except Exception as e:
            print(f"[POST] failed mode=image retry={attempt + 1}/{max_retries} error={e}")
            time.sleep(5)
    return False


def post_with_optional_image(
    client_twitter: tweepy.Client,
    api_v1: tweepy.API,
    final_text: str,
    source_text: str,
    source_tweet_id: int,
) -> Tuple[bool, str]:
    if not should_generate_image(source_text):
        success = post_to_twitter(client_twitter, final_text)
        return success, "text"

    os.makedirs("images", exist_ok=True)
    image_path = os.path.join("images", f"tmp_{source_tweet_id}.png")
    try:
        prompt = build_imagefx_prompt_from_tweet(source_text)
        generate_image_fx(prompt, image_path, size="1600x900")
    except Exception as e:
        print(f"[POST] image_generation_failed tweet_id={source_tweet_id} error={e} fallback=text")
        success = post_to_twitter(client_twitter, final_text)
        return success, "text_fallback"

    success = post_to_twitter_with_image(
        client_twitter,
        api_v1,
        final_text,
        image_path,
        alt_text="AI generated image related to the tweet content",
    )
    if success:
        return True, "image"

    print(f"[POST] image_post_failed tweet_id={source_tweet_id} fallback=text")
    fallback_success = post_to_twitter(client_twitter, final_text)
    return fallback_success, "text_fallback"
