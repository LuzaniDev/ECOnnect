import os
import sys
from pathlib import Path

from dotenv import load_dotenv


def _resolve_env() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent / ".env"
    return Path(__file__).parent.parent.parent / "backend" / ".env"


load_dotenv(_resolve_env())


class Settings:
    _econnect_port = os.getenv("ECONNECT_PORT", "9899")
    API_URL: str = os.getenv("ECONNECT_API_URL") or f"http://127.0.0.1:{_econnect_port}"

    FB_DATABASE: str | None = os.getenv("FB_DATABASE")
    FB_USER: str | None = os.getenv("FB_USER")
    FB_PASSWORD: str | None = os.getenv("FB_PASSWORD")

    MAX_BATCH_SIZE: int = int(os.getenv("MAX_BATCH_SIZE", "50"))


settings = Settings()
