import sys
import os
os.environ["PYI_SIGNATURE_MODULE"] = ""
if sys.stderr is None:
    import io
    sys.stderr = io.StringIO()
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
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S,%f")[:-3]
    with open(_log_file, "a", encoding="utf-8") as f:
        f.write(f"{ts} [{level}] ECOnnect: {msg}\n")
        f.flush()


import uvicorn
from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtGui import QIcon
from PySide6.QtCore import Qt


_ECONNECT_PORT = int(os.getenv("ECONNECT_PORT", "9899"))
_server_ready = threading.Event()
_server_failed = threading.Event()


def start_server():
    t_start = time.time()
    try:
        _log_raw(f"[SERVER] start_server() iniciado")
        _log_raw(f"[SERVER] sys.executable = {sys.executable!r}")
        _log_raw(f"[SERVER] sys.executable.parent = {Path(sys.executable).parent!r}")
        _log_raw(f"[SERVER] sys._MEIPASS = {getattr(sys, '_MEIPASS', 'N/A')}")
        _log_raw(f"[SERVER] sys.path = {sys.path}")
        _log_raw(f"[SERVER] frozen = {getattr(sys, 'frozen', False)}")
        _log_raw(f"[SERVER] cwd = {os.getcwd()}")
        _log_raw(f"[SERVER] log_file = {_log_file}")

        _log_raw(f"[SERVER] Importando backend.app.main...")
        import backend.app.main
        _log_raw(f"[SERVER] backend.app.main importado com sucesso ({(time.time()-t_start):.2f}s)")

        _log_raw(f"[SERVER] Chamando uvicorn.run()...")
        t_uv = time.time()
        uvicorn.run(
            backend.app.main.app,
            host="127.0.0.1",
            port=_ECONNECT_PORT,
            log_level="info",
            access_log=False,
            log_config=None,
        )
        _log_raw(f"[SERVER] uvicorn.run() RETORNOU apos {(time.time()-t_uv):.2f}s", "WARNING")
        _log_raw(f"[SERVER] servidor foi encerrado inesperadamente", "ERROR")
        _server_failed.set()
    except BaseException as e:
        elapsed = time.time() - t_start
        _log_raw(f"[SERVER] Excecao em start_server() apos {elapsed:.2f}s: {e}", "ERROR")
        try:
            _log_raw(f"[SERVER] TRACEBACK:\n{traceback.format_exc()}", "ERROR")
        except Exception:
            pass
        _server_failed.set()


def wait_for_server(timeout: int = 30) -> bool:
    import httpx

    _log_raw(f"[SERVER] wait_for_server() timeout={timeout}s, poll=0.2s")

    for i in range(timeout * 5):
        if _server_failed.is_set():
            _log_raw(f"[SERVER] _server_failed sinalizado na iteracao {i+1}", "ERROR")
            return False
        try:
            t0 = time.time()
            resp = httpx.get(f"http://127.0.0.1:{_ECONNECT_PORT}/health", timeout=2)
            elapsed = time.time() - t0
            if resp.status_code == 200:
                _log_raw(f"[SERVER] health=200 na iteracao {i+1} ({elapsed:.2f}s)")
                _server_ready.set()
                return True
            else:
                _log_raw(f"[SERVER] health={resp.status_code} ({elapsed:.2f}s)")
        except Exception as e:
            if i == 0 or i == timeout * 5 - 1:
                _log_raw(f"[SERVER] health exception na iteracao {i+1}: {type(e).__name__}: {e}")
        if i % 25 == 0:
            _log_raw(f"[SERVER] Aguardando servidor... iteracao {i+1}/{(timeout*5)}")
        time.sleep(0.2)

    _log_raw(f"[SERVER] Servidor nao respondeu apos {timeout}s", "ERROR")
    return False


def _ensure_env_file():
    if not getattr(sys, "frozen", False):
        _log_raw("[ENV] Nao congelado, pulando _ensure_env_file()")
        return

    exe_dir = Path(sys.executable).parent
    env_exe = exe_dir / ".env"
    _log_raw(f"[ENV] exe_dir = {exe_dir}")
    _log_raw(f"[ENV] env_exe = {env_exe}")
    _log_raw(f"[ENV] env_exe.exists() = {env_exe.exists()}")

    if env_exe.exists():
        _log_raw(f"[ENV] .env ja existe em {env_exe}, mantendo")
        return

    example = Path(sys._MEIPASS) / ".env.example"
    _log_raw(f"[ENV] example = {example}, exists={example.exists()}")

    if example.exists():
        import shutil
        import uuid
        shutil.copy2(str(example), str(env_exe))
        _log_raw(f"[ENV] .env.example copiado para {env_exe}")
        text = env_exe.read_text(encoding="utf-8")
        jwt = uuid.uuid4().hex + uuid.uuid4().hex
        text = text.replace("JWT_SECRET=", f"JWT_SECRET={jwt}")
        text = text.replace("DB_PASSWORD=", "DB_PASSWORD=postgres")
        text = text.replace("DB_USER=econnect", "DB_USER=postgres")
        env_exe.write_text(text, encoding="utf-8")
        _log_raw(f"[ENV] JWT_SECRET gerado e DB_USER=postgres, DB_PASSWORD=postgres definidos")
        _log_raw(f"[ENV] .env criado de .env.example: {env_exe}")
    else:
        _log_raw(f"[ENV] .env.example NAO ENCONTRADO em MEIPASS!", "CRITICAL")
        _log_raw(f"[ENV] MEIPASS={sys._MEIPASS}", "CRITICAL")
        _log_raw(f"[ENV] Listing MEIPASS root:")
        try:
            for f in Path(sys._MEIPASS).iterdir():
                _log_raw(f"[ENV]   {f.name}")
        except Exception as e2:
            _log_raw(f"[ENV]   erro listing: {e2}", "ERROR")


def _validate_env_file() -> bool:
    if getattr(sys, "frozen", False):
        env_file = Path(sys.executable).parent / ".env"
    else:
        env_file = Path(__file__).parent.parent / "backend" / ".env"
    if not env_file.exists():
        env_file = Path(__file__).parent.parent / ".env"

    _log_raw(f"[ENV] _validate_env_file() path = {env_file}, exists={env_file.exists()}")

    if not env_file.exists():
        _log_raw(f"[ENV] ARQUIVO .env NAO EXISTE", "ERROR")
        return False

    lines = env_file.read_text(encoding="utf-8").splitlines()
    vals = {}
    for line in lines:
        if "=" in line and not line.startswith("#"):
            k, _, v = line.partition("=")
            vals[k.strip()] = v.strip()

    _log_raw(f"[ENV] Campos encontrados no .env: {list(vals.keys())}")

    required = ["DB_HOST", "DB_PORT", "DB_USER", "DB_PASSWORD", "DB_NAME", "JWT_SECRET",
                 "FB_DATABASE", "FB_USER", "FB_PASSWORD"]
    missing = []
    for k in required:
        v = vals.get(k)
        if not v:
            missing.append(k)
            _log_raw(f"[ENV] Campo OBRIGATORIO faltando: {k}", "ERROR")

    if missing:
        _log_raw(f"[ENV] Campos obrigatorios faltando: {missing}", "ERROR")
        return False

    _log_raw(f"[ENV] Validacao OK - DB_USER={vals['DB_USER']} DB_HOST={vals['DB_HOST']} DB_PORT={vals['DB_PORT']} DB_NAME={vals['DB_NAME']}")
    _log_raw(f"[ENV] DB_PASSWORD={'****' if vals.get('DB_PASSWORD') else 'VAZIO!'}")
    _log_raw(f"[ENV] JWT_SECRET={vals['JWT_SECRET'][:8] + '...' if vals.get('JWT_SECRET') else 'VAZIO!'}")
    return True


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
        logger.info("Python: %s", sys.version)

        _ensure_env_file()

        if not _validate_env_file():
            logger.error("[ENV] .env invalido ou inexistente")
            app = _create_app_instance()
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Information)
            msg.setWindowTitle("ECOnnect — Configuracao necessaria")
            msg.setText(
                "O arquivo .env nao esta configurado.\n\n"
                "Execute o ECOnnect Configurador primeiro para\n"
                "configurar o banco de dados e o Firebird."
            )
            msg.setWindowFlags(msg.windowFlags() | Qt.WindowStaysOnTopHint)
            msg.raise_()
            msg.activateWindow()
            msg.exec()
            sys.exit(1)

        os.environ.setdefault("QT_QPA_PLATFORM", "windows")

        _log_raw("[PORT] Verificando porta 9899...")
        import subprocess
        try:
            result = subprocess.run(
                ["netstat", "-ano", "|", "findstr", ":9899"],
                capture_output=True, text=True, shell=True, timeout=5
            )
            for line in result.stdout.splitlines():
                parts = line.strip().split()
                if len(parts) >= 5 and parts[1].endswith(":9899") and parts[3].endswith(":9899"):
                    pid = parts[4]
                    _log_raw(f"[PORT] Matando processo PID {pid} na porta 9899")
                    subprocess.run(["taskkill", "/F", "/PID", pid], capture_output=True, timeout=5)
            time.sleep(1)
        except Exception as e:
            _log_raw(f"[PORT] Erro ao verificar porta: {e}", "WARNING")

        logger.info("[SERVER] Iniciando thread do servidor...")
        server_thread = threading.Thread(target=start_server, daemon=True)
        server_thread.start()
        logger.info("[SERVER] Thread do servidor iniciada, aguardando...")

        t_wait = time.time()
        if not wait_for_server():
            elapsed = time.time() - t_wait
            _log_raw(f"[SERVER] wait_for_server() retornou False apos {elapsed:.1f}s", "CRITICAL")
            _log_raw(f"[SERVER] server_thread.is_alive() = {server_thread.is_alive()}", "CRITICAL")
            _log_raw(f"[SERVER] _server_ready.is_set() = {_server_ready.is_set()}", "CRITICAL")
            _log_raw(f"[SERVER] _server_failed.is_set() = {_server_failed.is_set()}", "CRITICAL")

            app = _create_app_instance()
            _log_raw("[SERVER] Exibindo dialogo de erro para o usuario", "ERROR")
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Critical)
            msg.setWindowTitle("Erro de inicializacao")
            msg.setText(
                "Nao foi possivel iniciar o servidor.\n\n"
                "Verifique se o PostgreSQL esta rodando e se o\n"
                "arquivo .env foi configurado corretamente.\n\n"
                "Execute o ECOnnect Configurador para revisar.\n\n"
                "Consulte o arquivo econnect.log para detalhes."
            )
            msg.setWindowFlags(msg.windowFlags() | Qt.WindowStaysOnTopHint)
            msg.raise_()
            msg.activateWindow()
            msg.exec()
            sys.exit(1)

        _log_raw(f"[SERVER] Servidor pronto em {(time.time()-t_wait):.1f}s!")
        logger.info("[SERVER] Servidor backend pronto!")
        app = _create_app_instance()

        from frontend.app.core.theme import apply_palette, theme_manager, _set_titlebar_theme
        apply_palette(theme_manager.current())

        from frontend.app.app import MainWindow
        window = MainWindow()
        window.show()
        _set_titlebar_theme(int(window.winId()), theme_manager.current().titlebar_dark)
        window.raise_()
        window.activateWindow()
        logger.info("[APP] Janela principal exibida")

        sys.exit(app.exec())

    except SystemExit:
        raise
    except Exception:
        logger.critical("[APP] Excecao nao tratada no main():")
        logger.critical(traceback.format_exc())
        try:
            app = _create_app_instance()
            from frontend.app.widgets.dialogs import show_error
            show_error(None, "Erro critico",
                       "Ocorreu um erro inesperado.\n"
                       "Verifique o arquivo econnect.log para detalhes.")
            app.exec()
        except Exception:
            pass
        sys.exit(1)


if __name__ == "__main__":
    main()
