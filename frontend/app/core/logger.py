from datetime import datetime
from collections import deque
from PySide6.QtCore import QObject, Signal


class LogSignal(QObject):
    emitted = Signal(str)


class AppLogger:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._buffer: deque[str] = deque(maxlen=5000)
        self._signal = LogSignal()
        self._info("LOGGER", "Sistema de logs iniciado")

    @property
    def emitted(self):
        return self._signal.emitted

    def _format(self, level: str, source: str, line: int, message: str, context: dict | None = None) -> str:
        ts = datetime.now().strftime("%H:%M:%S.%f")[:11]
        ctx = ""
        if context:
            ctx = "  │  " + ", ".join(f"{k}={v!r}" for k, v in context.items())
        return f"[{ts}] [{level:7s}] {source}:{line} → {message}{ctx}"

    def _emit(self, level: str, source: str, line: int, message: str, context: dict | None = None):
        entry = self._format(level, source, line, message, context)
        self._buffer.append(entry)
        self._signal.emitted.emit(entry)

    def _info(self, source: str, message: str, **context):
        self._emit("INFO", source, 0, message, context or None)

    def info(self, source: str, message: str, line: int = 0, **context):
        self._emit("INFO", source, line, message, context or None)

    def warning(self, source: str, message: str, line: int = 0, **context):
        self._emit("WARN", source, line, message, context or None)

    def error(self, source: str, message: str, line: int = 0, **context):
        self._emit("ERROR", source, line, message, context or None)

    def get_buffer(self) -> list[str]:
        return list(self._buffer)

    def clear_buffer(self):
        self._buffer.clear()
        self._info("LOGGER", "Buffer de logs limpo")


logger = AppLogger()
