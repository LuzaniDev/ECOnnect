import sys
import threading
from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication


class _SignalRelay(QObject):
    success = Signal(object)
    error = Signal(str)


_keepalive = []


def run_in_thread(fn, on_success, on_error=None, parent_window=None, *args, **kwargs):
    from frontend.app.widgets.loading_popup import LoadingPopup

    loading = None
    if parent_window is not None:
        loading = LoadingPopup(parent_window)
        loading.show()
        QApplication.processEvents()

    relay = _SignalRelay()
    closed = [False]

    def _close_loading():
        if closed[0]:
            return
        closed[0] = True
        if loading is not None:
            try:
                loading.hide()
                loading.deleteLater()
            except RuntimeError:
                pass

    def _cleanup_relay():
        try:
            _keepalive.remove(relay)
        except ValueError:
            pass

    def _wrapped_success(result):
        _close_loading()
        _cleanup_relay()
        on_success(result)

    def _wrapped_error(msg):
        _close_loading()
        _cleanup_relay()
        if on_error:
            on_error(msg)
        else:
            from frontend.app.core.logger import logger
            logger.error("WORKER", msg, line=16)

    relay.success.connect(_wrapped_success)
    relay.error.connect(_wrapped_error)

    _keepalive.append(relay)

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
    return thread
