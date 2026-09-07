from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "ICEux Songbird Radio"
    app_env: str = "development"
    admin_username: str = "admin"
    admin_password: str = ""
    session_secret: str = "development-only-change-me"
    database_url: str = "sqlite:///./data/iceux.db"
    icecast_host: str = "localhost"
    icecast_port: int = 8000
    icecast_mount: str = "/radio"
    icecast_format: str = "mp3"
    icecast_bitrate: int = 128
    liquidsoap_host: str = "127.0.0.1"
    liquidsoap_port: int = 1234
    liquidsoap_socket: str = ""

    @property
    def production(self) -> bool:
        return self.app_env.lower() == "production"

    def ensure_directories(self) -> None:
        Path("data/emergency").mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_directories()
    return settings
