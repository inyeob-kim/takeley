"""Worker-only TTS helpers (OpenAI speech). Kept for future column / Issue audio."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path

from app.core.config import get_settings

logger = logging.getLogger(__name__)

# OpenAI speech input soft limit is 4096 characters.
_MAX_CHARS = 3800


@dataclass
class AudioResult:
    audio_url: str | None
    audio_status: str  # none | ready | failed
    path: Path | None = None


def brief_audio_path(user_id: str, brief_date: str) -> Path:
    settings = get_settings()
    root = Path(settings.brief_audio_dir)
    if not root.is_absolute():
        # Resolve relative to backend/ working directory.
        root = Path.cwd() / root
    return root / user_id / f"{brief_date}.mp3"


def public_audio_url(user_id: str, brief_date: str) -> str:
    return f"/api/v1/brief/audio/{user_id}/{brief_date}"


def _chunk_transcript(text: str) -> list[str]:
    text = (text or "").strip()
    if not text:
        return []
    if len(text) <= _MAX_CHARS:
        return [text]

    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    if not paragraphs:
        paragraphs = [text]

    chunks: list[str] = []
    current = ""
    for para in paragraphs:
        if len(para) > _MAX_CHARS:
            # Hard-split oversized paragraph.
            for i in range(0, len(para), _MAX_CHARS):
                piece = para[i : i + _MAX_CHARS].strip()
                if piece:
                    if current:
                        chunks.append(current)
                        current = ""
                    chunks.append(piece)
            continue
        candidate = f"{current}\n\n{para}".strip() if current else para
        if len(candidate) <= _MAX_CHARS:
            current = candidate
        else:
            if current:
                chunks.append(current)
            current = para
    if current:
        chunks.append(current)
    return chunks


def synthesize_brief_audio(
    transcript: str,
    *,
    user_id: str,
    brief_date: str,
    voice: str | None = None,
) -> AudioResult:
    settings = get_settings()
    if not settings.tts_enabled:
        return AudioResult(audio_url=None, audio_status="none")
    if not settings.openai_api_key:
        logger.warning("tts skipped reason=no_openai_key")
        return AudioResult(audio_url=None, audio_status="failed")
    if not (transcript or "").strip():
        return AudioResult(audio_url=None, audio_status="none")

    chunks = _chunk_transcript(transcript)
    if not chunks:
        return AudioResult(audio_url=None, audio_status="none")

    tts_voice = (voice or settings.tts_voice or "nova").strip() or "nova"
    out_path = brief_audio_path(user_id, brief_date)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        from openai import OpenAI

        client = OpenAI(api_key=settings.openai_api_key)
        audio_parts: list[bytes] = []
        from app.core.usage import TTS_CHARACTERS, record_usage

        for i, chunk in enumerate(chunks):
            record_usage(
                TTS_CHARACTERS,
                len(chunk),
                tags={"model": settings.tts_model, "voice": tts_voice},
                scope_type="user",
                user_id=user_id,
            )
            resp = client.audio.speech.create(
                model=settings.tts_model,
                voice=tts_voice,
                input=chunk,
                response_format="mp3",
            )
            # openai SDK: resp.content is bytes for speech
            data = getattr(resp, "content", None)
            if data is None and hasattr(resp, "read"):
                data = resp.read()
            if not data:
                raise RuntimeError(f"empty TTS response chunk={i}")
            audio_parts.append(data)
            logger.info(
                "tts_chunk ok model=%s voice=%s chunk=%s/%s chars=%s",
                settings.tts_model,
                tts_voice,
                i + 1,
                len(chunks),
                len(chunk),
            )

        out_path.write_bytes(b"".join(audio_parts))
        url = public_audio_url(user_id, brief_date)
        logger.info(
            "tts_ready user=%s date=%s voice=%s bytes=%s path=%s",
            user_id,
            brief_date,
            tts_voice,
            out_path.stat().st_size,
            out_path,
        )
        return AudioResult(audio_url=url, audio_status="ready", path=out_path)
    except Exception:
        logger.exception("tts failed user=%s date=%s", user_id, brief_date)
        return AudioResult(audio_url=None, audio_status="failed")
