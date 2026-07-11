import sys
import datetime
from pathlib import Path


def _backend_log_config(msg: str, level: str = "INFO") -> None:
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S,%f")[:-3]
    try:
        if getattr(sys, "frozen", False):
            log_file = Path(sys.executable).parent / "econnect.log"
        else:
            log_file = Path(__file__).parent.parent.parent / "econnect.log"
        with open(str(log_file), "a", encoding="utf-8") as f:
            f.write(f"{ts} [{level}] CONFIG: {msg}\n")
            f.flush()
    except Exception:
        pass


def _resolve_env_file() -> Path:
    if getattr(sys, "frozen", False):
        result = Path(sys.executable).parent / ".env"
        _backend_log_config(f"_resolve_env_file() (frozen): {result} | exists={result.exists()}")
        return result
    result = Path(__file__).parent.parent / ".env"
    _backend_log_config(f"_resolve_env_file() (source): {result} | exists={result.exists()}")
    return result


from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_resolve_env_file(),
        extra="ignore",
    )

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

    MAX_BATCH_SIZE: int = 50

    @property
    def DATABASE_URL(self) -> str:
        return f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}?ssl=disable"
        extra = "ignore"


_backend_log_config("Criando instancia Settings...")
try:
    settings = Settings()
    _backend_log_config(f"Settings criado OK")
    _backend_log_config(f"DB_HOST={settings.DB_HOST} DB_PORT={settings.DB_PORT} DB_USER={settings.DB_USER} DB_NAME={settings.DB_NAME}")
    _backend_log_config(f"DB_PASSWORD={'****' if settings.DB_PASSWORD else 'VAZIO!'}")
    _backend_log_config(f"JWT_SECRET={settings.JWT_SECRET[:8] + '...' if settings.JWT_SECRET else 'VAZIO!'}")
    preview = settings.DATABASE_URL.replace(settings.DB_PASSWORD, "****")
    _backend_log_config(f"DATABASE_URL={preview}")
    _backend_log_config(f"FB_DATABASE={settings.FB_DATABASE} FB_USER={settings.FB_USER}")
except Exception as e:
    _backend_log_config(f"FALHA ao criar Settings: {e}", "ERROR")
    import traceback
    _backend_log_config(traceback.format_exc(), "ERROR")
    raise
