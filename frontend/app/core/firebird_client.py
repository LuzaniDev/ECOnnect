import sys
import os
import datetime
import logging
import fdb
from pathlib import Path
from frontend.app.config import settings

_fb_log = logging.getLogger("firebird")


def _log_fb(msg: str, level: str = "INFO") -> None:
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S,%f")[:-3]
    exe_dir = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).parent.parent.parent.parent
    log_file = exe_dir / "econnect.log"
    with open(str(log_file), "a", encoding="utf-8") as f:
        f.write(f"{ts} [{level}] firebird: {msg}\n")
        f.flush()


class FirebirdClient:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._connection = None
            cls._instance._dsn = settings.FB_DATABASE
            cls._instance._user = settings.FB_USER
            cls._instance._password = settings.FB_PASSWORD
            _log_fb(f"Configurado: dsn={settings.FB_DATABASE!r}, user={settings.FB_USER!r}")
        return cls._instance

    def configure(self, dsn: str | None = None, user: str | None = None, password: str | None = None):
        if dsn is not None:
            self._dsn = dsn
        if user is not None:
            self._user = user
        if password is not None:
            self._password = password
        _log_fb(f"Reconfigurado: dsn={self._dsn!r}, user={self._user!r}")
        self.fechar()

    def conectar(self):
        if self._connection is not None:
            try:
                self._connection.ping()
                return self._connection
            except Exception as e:
                _log_fb(f"Ping falhou, reconectando: {e}", "WARNING")
                self._connection = None

        _log_fb(f"Conectando Firebird: dsn={self._dsn!r}, user={self._user!r}")
        try:
            self._connection = fdb.connect(
                dsn=self._dsn,
                user=self._user,
                password=self._password,
                charset="WIN1252",
            )
            _log_fb("Conexao Firebird estabelecida")
        except Exception as e:
            _log_fb(f"Falha ao conectar Firebird: {e}", "ERROR")
            raise
        return self._connection

    def executar(self, sql: str, params: tuple | None = None):
        conn = self.conectar()
        cursor = conn.cursor()
        try:
            if params:
                cursor.execute(sql, params)
            else:
                cursor.execute(sql)
            conn.commit()
            return cursor
        except Exception:
            conn.rollback()
            raise

    def query(self, sql: str, params: tuple | None = None) -> list:
        conn = self.conectar()
        cursor = conn.cursor()
        try:
            if params:
                cursor.execute(sql, params)
            else:
                cursor.execute(sql)
            rows = cursor.fetchall()
            cursor.close()
            return rows
        except Exception:
            cursor.close()
            raise

    def executar_um(self, sql: str, params: tuple | None = None):
        conn = self.conectar()
        cursor = conn.cursor()
        try:
            if params:
                cursor.execute(sql, params)
            else:
                cursor.execute(sql)
            row = cursor.fetchone()
            cursor.close()
            conn.commit()
            return row
        except Exception:
            conn.rollback()
            cursor.close()
            raise

    def query_with_columns(self, sql: str, params: tuple | None = None) -> tuple[list[str], list[tuple]]:
        conn = self.conectar()
        cursor = conn.cursor()
        try:
            if params:
                cursor.execute(sql, params)
            else:
                cursor.execute(sql)
            col_names = [desc[0] for desc in cursor.description] if cursor.description else []
            rows = cursor.fetchall()
            cursor.close()
            return col_names, rows
        except Exception:
            cursor.close()
            raise

    def fechar(self):
        if self._connection:
            try:
                self._connection.close()
            except Exception:
                pass
            self._connection = None

    @property
    def connection(self):
        return self.conectar()


fb = FirebirdClient()
