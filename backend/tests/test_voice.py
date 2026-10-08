import httpx

from backend.services import voice as voice_svc


def test_tts_reports_provider_auth_failures_without_exposing_key(monkeypatch):
    api_key = "test-secret-key"
    monkeypatch.setattr(
        voice_svc,
        "get_settings",
        lambda: type(
            "Settings",
            (),
            {
                "has_elevenlabs": True,
                "elevenlabs_voice_id": "test-voice",
                "elevenlabs_tts_model": "eleven_multilingual_v2",
                "elevenlabs_api_key": api_key,
                "http_timeout": 1,
            },
        )(),
    )
    response = httpx.Response(
        401,
        json={"detail": {"status": "invalid_api_key", "message": f"Invalid key: {api_key}"}},
        request=httpx.Request("POST", "https://api.elevenlabs.io/v1/text-to-speech/test-voice"),
    )

    class FakeClient:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def post(self, *args, **kwargs):
            return response

    monkeypatch.setattr(voice_svc.httpx, "Client", FakeClient)

    try:
        voice_svc.tts("auth failure test")
    except voice_svc.VoiceError as exc:
        assert "HTTP 401" in str(exc)
        assert "API key" in str(exc)
        assert api_key not in str(exc)
    else:
        raise AssertionError("TTS must report upstream authentication failures")
