import sys
from pathlib import Path

from pydantic_settings import BaseSettings


def _resolve_env_file() -> Path:
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).parent
        exe_env = exe_dir / ".env"
        if exe_env.exists():
            return exe_env
        return Path(sys._MEIPASS) / "backend" / ".env"
    return Path(__file__).parent.parent / ".env"


class Settings(BaseSettings):
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_USER: str = "econnect"
    DB_PASSWORD: str
    DB_NAME: str = "econnect_db"
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_MINUTES: int = 1440

    FB_DATABASE: str
    FB_USER: str
    FB_PASSWORD: str

    @property
    def DATABASE_URL(self) -> str:
        return f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}?ssl=disable"

    class Config:
        env_file = _resolve_env_file()


settings = Settings()
