"""Environment configuration for PathWay."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Load API keys and model names from `.env`."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    gemini_api_key: str = ""
    google_api_key: str = ""
    anthropic_api_key: str = ""
    llm_model: str = "gemini-2.5-flash"

    elevenlabs_api_key: str = ""
    elevenlabs_voice_id: str = "JBFqnCBsd6RMkjVDRZzb"
    elevenlabs_stt_model: str = "scribe_v1"
    elevenlabs_tts_model: str = "eleven_multilingual_v2"

    reed_api_key: str = ""
    http_timeout: float = 45.0

    @property
    def google_key(self) -> str:
        """Gemini Studio key (GEMINI_API_KEY or GOOGLE_API_KEY)."""
        return self.gemini_api_key or self.google_api_key

    @property
    def has_llm(self) -> bool:
        return bool(self.google_key or self.anthropic_api_key)

    @property
    def has_elevenlabs(self) -> bool:
        return bool(self.elevenlabs_api_key)

    @property
    def has_reed(self) -> bool:
        return bool(self.reed_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
