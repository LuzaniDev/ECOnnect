import sys
import threading
from PySide6.QtCore import QObject, Signal


class _SignalRelay(QObject):
    success = Signal(object)
    error = Signal(str)


_keepalive = []


def run_in_thread(fn, on_success, on_error=None, *args, **kwargs):
    relay = _SignalRelay()
    relay.success.connect(on_success)
    if on_error:
        relay.error.connect(on_error)
    else:
        from frontend.app.core.logger import logger
        relay.error.connect(lambda e: logger.error("WORKER", str(e), line=16))

    _keepalive.append(relay)

    def _cleanup():
        try:
            _keepalive.remove(relay)
        except ValueError:
            pass

    def _run():
        try:
            result = fn(*args, **kwargs)
            relay.success.emit(result)
        except Exception as e:
            try:
                relay.error.emit(str(e))
            except Exception:
                print(f"[WORKER] Erro no relay.error.emit: {e}", file=sys.stderr)

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    threading.Timer(5.0, _cleanup).start()
    return thread

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    return thread
