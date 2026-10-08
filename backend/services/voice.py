"""ElevenLabs STT (Scribe) and TTS. Keys stay on the server."""

from __future__ import annotations

import hashlib
import logging

import httpx

from backend.config import get_settings

logger = logging.getLogger("pathway.voice")

STT_URL = "https://api.elevenlabs.io/v1/speech-to-text"
TTS_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"

# In-memory cache so demo replays do not burn credits.
_TTS_CACHE: dict[str, bytes] = {}


class VoiceError(RuntimeError):
    pass


def stt(audio: bytes, filename: str, content_type: str, language_code: str | None = None) -> dict[str, str]:
    """Transcribe user speech via ElevenLabs Scribe (multipart)."""
    settings = get_settings()
    if not settings.has_elevenlabs:
        raise VoiceError("ElevenLabs is not configured. Use text mode.")
    data = {"model_id": settings.elevenlabs_stt_model}
    if language_code:
        data["language_code"] = language_code
    files = {"file": (filename or "audio.webm", audio, content_type or "audio/webm")}
    headers = {"xi-api-key": settings.elevenlabs_api_key}
    with httpx.Client(timeout=settings.http_timeout) as client:
        resp = client.post(STT_URL, headers=headers, data=data, files=files)
        if resp.status_code == 429:
            raise VoiceError("Voice is busy (rate limit). Please type your answer.")
        resp.raise_for_status()
        payload = resp.json()
    return {
        "text": payload.get("text") or "",
        "language_code": payload.get("language_code") or (language_code or ""),
    }


def tts(text: str, voice_id: str | None = None, speed: float | None = None) -> bytes:
    """Synthesise speech. Cached by text+voice+speed."""
    settings = get_settings()
    if not settings.has_elevenlabs:
        raise VoiceError("ElevenLabs is not configured. Use text mode.")
    vid = voice_id or settings.elevenlabs_voice_id
    speed_val = 0.85 if speed is None else speed
    key = hashlib.sha256(f"{vid}|{speed_val}|{text}".encode("utf-8")).hexdigest()
    if key in _TTS_CACHE:
        return _TTS_CACHE[key]
    url = TTS_URL.format(voice_id=vid)
    headers = {
        "xi-api-key": settings.elevenlabs_api_key,
        "Content-Type": "application/json",
        "Accept": "audio/mpeg",
    }
    body: dict = {
        "text": text[:4000],
        "model_id": settings.elevenlabs_tts_model,
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.75,
            "speed": max(0.7, min(1.2, speed_val)),
        },
    }
    try:
        with httpx.Client(timeout=settings.http_timeout) as client:
            resp = client.post(url, headers=headers, json=body, params={"output_format": "mp3_44100_128"})
            if resp.status_code == 429:
                raise VoiceError("Voice is busy (rate limit). Please read the text instead.")
            try:
                resp.raise_for_status()
            except httpx.HTTPStatusError as exc:
                if resp.status_code == 404 and vid != "JBFqnCBsd6RMkjVDRZzb":
                    logger.warning("Voice ID %s not found on ElevenLabs, retrying with default voice...", vid)
                    return tts(text, voice_id="JBFqnCBsd6RMkjVDRZzb", speed=speed)
                try:
                    detail = resp.json().get("detail", {})
                    provider_message = detail.get("message", "") if isinstance(detail, dict) else str(detail)
                except ValueError:
                    provider_message = ""
                provider_message = str(provider_message)[:300]
                if settings.elevenlabs_api_key:
                    provider_message = provider_message.replace(settings.elevenlabs_api_key, "[redacted]")
                logger.warning(
                    "ElevenLabs TTS rejected the request (HTTP %s): %s",
                    resp.status_code,
                    provider_message or "no provider detail",
                )
                if resp.status_code in {401, 403}:
                    message = "Check the ElevenLabs API key and voice permissions."
                elif resp.status_code == 404:
                    message = "Check that the configured ElevenLabs voice ID exists."
                else:
                    message = provider_message or "The provider rejected the speech request."
                raise VoiceError(f"ElevenLabs TTS failed (HTTP {resp.status_code}). {message}") from exc
            audio = resp.content
    except httpx.RequestError as exc:
        raise VoiceError(f"Network error connecting to ElevenLabs: {exc}") from exc
    if len(_TTS_CACHE) > 64:
        _TTS_CACHE.clear()
    _TTS_CACHE[key] = audio
    return audio
