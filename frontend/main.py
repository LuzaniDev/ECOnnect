import sys
import os
import datetime
import traceback
import threading
import time
import logging
from pathlib import Path

_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if getattr(sys, 'frozen', False):
    _BASE = sys._MEIPASS

sys.path.insert(0, _BASE)
sys.path.insert(0, os.path.join(_BASE, "backend"))
sys.path.insert(0, os.path.join(_BASE, "frontend"))

if getattr(sys, 'frozen', False):
    _log_dir = Path(sys.executable).parent
else:
    _log_dir = Path(os.path.dirname(os.path.abspath(__file__)))
_log_file = str(_log_dir / "econnect.log")

_log_handler = logging.FileHandler(_log_file, encoding="utf-8", mode="w")
_log_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))

root_logger = logging.getLogger()
root_logger.setLevel(logging.DEBUG)
root_logger.addHandler(_log_handler)
if not getattr(sys, 'frozen', False):
    _console_handler = logging.StreamHandler(sys.stdout)
    _console_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
    root_logger.addHandler(_console_handler)

logger = logging.getLogger("ECOnnect")


def _log_raw(msg: str, level: str = "INFO") -> None:
    """Write directly to log file, bypassing logging module."""
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S,%f")[:-3]
    with open(_log_file, "a", encoding="utf-8") as f:
        f.write(f"{ts} [{level}] ECOnnect: {msg}\n")
        f.flush()


import uvicorn
from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtGui import QIcon
from PySide6.QtCore import Qt


_ECONNECT_PORT = int(os.getenv("ECONNECT_PORT", "9899"))


def start_server():
    try:
        _log_raw("Importando backend.app.main...")
        import backend.app.main
        _log_raw("backend.app.main importado com sucesso")
        uvicorn.run(
            backend.app.main.app,
            host="127.0.0.1",
            port=_ECONNECT_PORT,
            log_level="warning",
            access_log=False,
            log_config=None,
        )
    except Exception as e:
        _log_raw(f"Falha ao iniciar servidor backend: {e}", "ERROR")
        try:
            import traceback as _tb
            _log_raw(_tb.format_exc(), "ERROR")
        except Exception:
            pass


def wait_for_server(timeout: int = 120) -> bool:
    import httpx

    for i in range(timeout):
        try:
            resp = httpx.get(f"http://127.0.0.1:{_ECONNECT_PORT}/health", timeout=5)
            if resp.status_code == 200:
                return True
        except Exception:
            pass
        if i % 5 == 0:
            _log_raw(f"Aguardando servidor... tentativa {i + 1}/{timeout}")
        time.sleep(1)
    _log_raw(f"Servidor n\u00e3o respondeu ap\u00f3s {timeout} tentativas", "ERROR")
    return False


def _ensure_env_file():
    if not getattr(sys, "frozen", False):
        return
    exe_dir = Path(sys.executable).parent
    env_exe = exe_dir / ".env"
    if env_exe.exists():
        return
    bundled = Path(sys._MEIPASS) / "backend" / ".env"
    example = Path(sys._MEIPASS) / ".env.example"
    if bundled.exists():
        import shutil
        shutil.copy2(str(bundled), str(env_exe))
        logger.info(".env copiado do bundle para %s", env_exe)
    elif example.exists():
        import shutil
        shutil.copy2(str(example), str(env_exe))
        logger.info(".env copiado de .env.example para %s", env_exe)


def _create_app_instance():
    app = QApplication(sys.argv)
    app.setApplicationName("ECOnnect")
    icon_path = os.path.join(_BASE, "frontend", "assets", "app_icon.ico")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    return app


def main():
    try:
        logger.info("=== ECOnnect iniciando ===")
        logger.info("Frozen: %s", getattr(sys, 'frozen', False))
        logger.info("Argv: %s", sys.argv)
        logger.info("EXE dir: %s", Path(sys.executable).parent if getattr(sys, 'frozen', False) else 'N/A')
        logger.info("Log file: %s", _log_file)
        logger.info("MEIPASS: %s", getattr(sys, '_MEIPASS', 'N/A'))
        logger.info("CWD: %s", os.getcwd())
        logger.info("PORT: %s", _ECONNECT_PORT)

        _ensure_env_file()

        os.environ.setdefault("QT_QPA_PLATFORM", "windows")

        _log_raw("Matando processos anteriores na porta 9899...")
        import subprocess
        result = subprocess.run(
            ["netstat", "-ano", "|", "findstr", ":9899"],
            capture_output=True, text=True, shell=True
        )
        for line in result.stdout.splitlines():
            parts = line.strip().split()
            if len(parts) >= 5 and parts[1].endswith(":9899") and parts[3].endswith(":9899"):
                pid = parts[4]
                _log_raw(f"Matando processo PID {pid} na porta 9899")
                subprocess.run(["taskkill", "/F", "/PID", pid], capture_output=True)
        time.sleep(1)

        logger.info("Iniciando thread do servidor...")
        server_thread = threading.Thread(target=start_server, daemon=True)
        server_thread.start()
        logger.info("Thread do servidor iniciada, aguardando...")

        if not wait_for_server():
            logger.error("Servidor backend não iniciou a tempo")
            app = _create_app_instance()
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Critical)
            msg.setWindowTitle("Erro de inicialização")
            msg.setText(
                "Não foi possível iniciar o servidor backend.\n"
                "Verifique se o PostgreSQL está rodando na rede."
            )
            msg.setWindowFlags(msg.windowFlags() | Qt.WindowStaysOnTopHint)
            msg.raise_()
            msg.activateWindow()
            msg.exec()
            sys.exit(1)

        logger.info("Servidor backend pronto!")
        app = _create_app_instance()

        from frontend.app.core.theme import apply_palette, theme_manager, _set_titlebar_theme
        apply_palette(theme_manager.current())

        from frontend.app.app import MainWindow
        window = MainWindow()
        window.show()
        _set_titlebar_theme(int(window.winId()), theme_manager.current().titlebar_dark)
        window.raise_()
        window.activateWindow()
        logger.info("Janela principal exibida")

        sys.exit(app.exec())

    except SystemExit:
        raise
    except Exception:
        logger.critical("Exceção não tratada no main():")
        logger.critical(traceback.format_exc())
        try:
            app = _create_app_instance()
            from frontend.app.widgets.dialogs import show_error
            show_error(None, "Erro crítico",
                       "Ocorreu um erro inesperado.\n"
                       "Verifique o arquivo econnect.log para detalhes.")
            app.exec()
        except Exception:
            pass
        sys.exit(1)


if __name__ == "__main__":
    main()