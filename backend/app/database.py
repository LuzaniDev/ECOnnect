import sys
import datetime
from pathlib import Path
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from .config import settings


def _db_log(msg: str, level: str = "INFO") -> None:
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S,%f")[:-3]
    try:
        if getattr(sys, "frozen", False):
            log_file = Path(sys.executable).parent / "econnect.log"
        else:
            log_file = Path(__file__).parent.parent.parent / "econnect.log"
        with open(str(log_file), "a", encoding="utf-8") as f:
            f.write(f"{ts} [{level}] DB: {msg}\n")
            f.flush()
    except Exception:
        pass


_db_log("Criando engine assincrona...")
_db_log(f"DATABASE_URL = {settings.DATABASE_URL.replace(settings.DB_PASSWORD, '****')}")
_db_log(f"echo = False")

engine = create_async_engine(settings.DATABASE_URL, echo=False)

_db_log("Engine criada com sucesso")
_db_log("Criando async_sessionmaker...")

async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

_db_log("async_sessionmaker criado")


class Base(DeclarativeBase):
    pass


_db_log("Base declarativa criada")


async def get_db():
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()
