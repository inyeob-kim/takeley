import os
import re
import time
import hashlib
import json
from pathlib import Path
from typing import Any, Tuple

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


def _build_text_fingerprint(text: str) -> str:
    normalized = re.sub(r"\s+", " ", (text or "").strip())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


def _duplicate_estimate(text: str) -> float:
    tokens = re.findall(r"\w+", (text or "").lower())
    if not tokens:
        return 0.0
    unique_count = len(set(tokens))
    return round(1.0 - (unique_count / len(tokens)), 3)


def _safe_response_text(error: Exception, max_len: int = 500) -> str:
    response = getattr(error, "response", None)
    if not response:
        return ""

    text = ""
    try:
        text = (response.text or "").strip()
    except Exception:
        text = ""

    if not text:
        try:
            text = json.dumps(response.json(), ensure_ascii=False)
        except Exception:
            text = ""

    text = text.replace("\n", " ").replace("\r", " ")
    return text[:max_len]


def _safe_api_errors(error: Exception) -> str:
    api_errors = getattr(error, "api_errors", None)
    if not api_errors:
        return ""
    try:
        return json.dumps(api_errors, ensure_ascii=False)
    except Exception:
        return str(api_errors)


def _safe_attr_json(error: Exception, attr_name: str) -> str:
    value = getattr(error, attr_name, None)
    if value in (None, "", []):
        return ""
    try:
        return json.dumps(value, ensure_ascii=False)
    except Exception:
        return str(value)


def _safe_error_dict(error: Exception) -> str:
    errors = getattr(error, "errors", None)
    if not errors:
        return ""
    try:
        return json.dumps(errors, ensure_ascii=False)
    except Exception:
        return str(errors)


def _extract_request_id(error: Exception) -> str:
    response = getattr(error, "response", None)
    if not response:
        return ""
    headers = getattr(response, "headers", {}) or {}
    return (
        headers.get("x-request-id", "")
        or headers.get("x-client-transaction-id", "")
        or headers.get("x-response-time", "")
    )


def _extract_status_code(error: Exception) -> Any:
    status_code = getattr(error, "status_code", None)
    if status_code is not None:
        return status_code
    response = getattr(error, "response", None)
    return getattr(response, "status_code", "unknown")


def _log_post_failure(
    *,
    mode: str,
    attempt: int,
    max_retries: int,
    text: str,
    error: Exception,
) -> None:
    print(
        f"[POST_DIAG] mode={mode} retry={attempt}/{max_retries} "
        f"error_type={type(error).__name__} "
        f"status_code={_extract_status_code(error)} "
        f"text_len={len(text)} "
        f"fingerprint={_build_text_fingerprint(text)} "
        f"duplicate_estimate={_duplicate_estimate(text)} "
        f"api_codes={_safe_attr_json(error, 'api_codes')} "
        f"api_messages={_safe_attr_json(error, 'api_messages')} "
        f"api_errors={_safe_api_errors(error)} "
        f"errors={_safe_error_dict(error)} "
        f"x_request_id={_extract_request_id(error)} "
        f"response_body={_safe_response_text(error)} "
        f"error={error}"
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
            _log_post_failure(
                mode="text",
                attempt=attempt + 1,
                max_retries=max_retries,
                text=text,
                error=e,
            )
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
            _log_post_failure(
                mode="image",
                attempt=attempt + 1,
                max_retries=max_retries,
                text=text,
                error=e,
            )
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
