from __future__ import annotations

import argparse
import ctypes
from functools import partial
import http.server
import logging
import os
from pathlib import Path
import secrets
import socket
import sys
import threading
import time
import urllib.request
import webbrowser

APP_NAME = "Nexyra CRM"
APP_FOLDER = "Nexyra CRM"
API_HOST = "127.0.0.1"
API_PORT = 8000
FRONTEND_HOST = "127.0.0.1"
FRONTEND_PORT = 5173
WINDOW_WIDTH = 1440
WINDOW_HEIGHT = 900
WINDOW_MIN_WIDTH = 1100
WINDOW_MIN_HEIGHT = 700


def resource_root() -> Path:
    bundled = getattr(sys, "_MEIPASS", None)
    if bundled:
        return Path(bundled)
    return Path(__file__).resolve().parent


def frontend_static_dir(root: Path) -> Path:
    if getattr(sys, "_MEIPASS", None):
        return root / "frontend_dist"
    return root / "frontend" / "dist"


def default_data_dir() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / APP_FOLDER
    return Path.home() / ".nexyra-crm"


def _sqlite_url(path: Path) -> str:
    return f"sqlite:///{path.resolve().as_posix()}"


def ensure_runtime_environment(data_dir: Path) -> tuple[Path, Path]:
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "logs").mkdir(parents=True, exist_ok=True)
    (data_dir / "webview").mkdir(parents=True, exist_ok=True)
    database_path = data_dir / "nexyra_crm.db"
    env_path = data_dir / ".env"

    if not env_path.exists():
        atlas_token = secrets.token_urlsafe(48)
        integration_key = secrets.token_urlsafe(48)
        env_path.write_text(
            "\n".join(
                [
                    "APP_NAME=Nexyra CRM",
                    "APP_VERSION=1.0.0",
                    "ENVIRONMENT=production",
                    "API_PREFIX=/api/v1",
                    f'DATABASE_URL="{_sqlite_url(database_path)}"',
                    "SQL_ECHO=false",
                    "CORS_ORIGINS=http://127.0.0.1:5173,http://localhost:5173",
                    "AUTH_SESSION_HOURS=12",
                    "AUTH_PASSWORD_ITERATIONS=600000",
                    "AUTH_SESSION_TOUCH_MINUTES=5",
                    "AUTH_LOGIN_MAX_ATTEMPTS=5",
                    "AUTH_LOCKOUT_MINUTES=15",
                    "AUTH_PASSWORD_RESET_MINUTES=30",
                    "AUTH_PASSWORD_RESET_COOLDOWN_SECONDS=60",
                    "AUTH_PASSWORD_RESET_DELIVERY=disabled",
                    "AUTH_PASSWORD_RESET_FRONTEND_URL=http://127.0.0.1:5173/reset-password",
                    "AUTH_SMTP_HOST=",
                    "AUTH_SMTP_PORT=587",
                    "AUTH_SMTP_USERNAME=",
                    "AUTH_SMTP_PASSWORD=",
                    "AUTH_SMTP_FROM=",
                    "AUTH_SMTP_STARTTLS=true",
                    "AUTH_SMTP_SSL=false",
                    "SECURITY_ALLOWED_HOSTS=127.0.0.1,localhost",
                    "SECURITY_RATE_LIMIT_ENABLED=true",
                    "SECURITY_LOGIN_REQUESTS_PER_MINUTE=30",
                    "SECURITY_PASSWORD_RECOVERY_REQUESTS_PER_MINUTE=10",
                    "SECURITY_PASSWORD_RESET_REQUESTS_PER_MINUTE=10",
                    "SECURITY_CHANGE_PASSWORD_REQUESTS_PER_MINUTE=10",
                    "SECURITY_EXTERNAL_INTAKE_REQUESTS_PER_MINUTE=120",
                    "SECURITY_DISABLE_DOCS_IN_PRODUCTION=true",
                    "SECURITY_REQUIRE_STRONG_SECRETS_IN_PRODUCTION=true",
                    "SECURITY_HSTS_ENABLED=false",
                    "SECURITY_HSTS_MAX_AGE_SECONDS=31536000",
                    "SECURITY_HSTS_INCLUDE_SUBDOMAINS=true",
                    "SECURITY_HSTS_PRELOAD=false",
                    f"INTEGRATION_SECRET_MASTER_KEY={integration_key}",
                    "META_APP_ID=",
                    "META_APP_SECRET=",
                    "META_WEBHOOK_VERIFY_TOKEN=",
                    "META_GRAPH_API_VERSION=v25.0",
                    "META_GRAPH_BASE_URL=https://graph.facebook.com",
                    "META_HTTP_TIMEOUT_SECONDS=10",
                    "WHATSAPP_APP_SECRET=",
                    "WHATSAPP_WEBHOOK_VERIFY_TOKEN=",
                    "WHATSAPP_META_APP_ID=",
                    "WHATSAPP_EMBEDDED_SIGNUP_CONFIG_ID=",
                    "WHATSAPP_GRAPH_API_VERSION=v25.0",
                    "WHATSAPP_GRAPH_BASE_URL=https://graph.facebook.com",
                    "WHATSAPP_HTTP_TIMEOUT_SECONDS=10",
                    "ATLAS_CONTRACT_VERSION=1.0",
                    f"ATLAS_INTEGRATION_TOKEN={atlas_token}",
                    "",
                ]
            ),
            encoding="utf-8",
        )

    os.chdir(data_dir)
    return env_path, database_path


def configure_logging(data_dir: Path) -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[
            logging.FileHandler(data_dir / "logs" / "launcher.log", encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )


def native_message(title: str, message: str, *, error: bool = False) -> None:
    if os.name == "nt":
        icon = 0x10 if error else 0x40
        try:
            ctypes.windll.user32.MessageBoxW(None, message, title, icon)
            return
        except Exception:
            logging.exception("Falha ao abrir caixa de mensagem nativa")
    logging.error("%s: %s", title, message) if error else logging.info(
        "%s: %s", title, message
    )


def run_migrations(root: Path) -> None:
    from alembic import command
    from alembic.config import Config

    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "alembic"))
    command.upgrade(config, "head")


def import_application():
    from app.main import app

    return app


def ensure_first_access(data_dir: Path) -> Path | None:
    from app.db.session import SessionLocal
    from app.repositories import UserCredentialRepository
    from app.schemas import WorkspaceCreate, WorkspaceUserCreate
    from app.services.user import WorkspaceUserService
    from app.services.workspace import WorkspaceService

    with SessionLocal() as db:
        if UserCredentialRepository(db).exists():
            return None

        workspace_service = WorkspaceService(db)
        workspaces = [item for item in workspace_service.list_all() if item.active]
        if workspaces:
            workspace = workspaces[0]
        else:
            workspace = workspace_service.create(
                WorkspaceCreate(
                    name="Minha Empresa",
                    slug="minha-empresa",
                    segment="generic",
                )
            )

        suffix = secrets.token_hex(3)
        email = f"admin-{suffix}@nexyra.local"
        password = f"Nx!{secrets.token_urlsafe(14)}9aA"
        WorkspaceUserService(db).create_member(
            workspace.public_id,
            WorkspaceUserCreate(
                name="Administrador Nexyra",
                email=email,
                role="admin",
                initial_password=password,
            ),
        )

    first_access_path = data_dir / "PRIMEIRO_ACESSO.txt"
    first_access_path.write_text(
        "\n".join(
            [
                "NEXYRA CRM — PRIMEIRO ACESSO",
                "",
                f"E-mail: {email}",
                f"Senha temporária: {password}",
                "",
                "Ao entrar, o Nexyra solicitará a troca da senha.",
                "Depois de trocar a senha, apague este arquivo.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return first_access_path


def port_is_free(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((host, port))
        except OSError:
            return False
    return True


def url_is_ready(url: str, timeout: float = 0.8) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return 200 <= response.status < 500
    except Exception:
        return False


def wait_for_url(url: str, timeout_seconds: float = 15.0) -> bool:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if url_is_ready(url):
            return True
        time.sleep(0.2)
    return False


class SpaHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        logging.debug("frontend: " + format, *args)

    def do_GET(self) -> None:  # noqa: N802 - assinatura da stdlib
        clean_path = self.path.split("?", 1)[0].split("#", 1)[0]
        if clean_path == "/":
            self.path = "/index.html"
        else:
            local_candidate = Path(self.directory) / clean_path.lstrip("/")
            if not local_candidate.exists():
                self.path = "/index.html"
        super().do_GET()


def start_frontend(static_dir: Path) -> http.server.ThreadingHTTPServer:
    if not (static_dir / "index.html").exists():
        raise RuntimeError(
            "Frontend compilado não encontrado. Gere `frontend/dist` antes do pacote."
        )

    handler = partial(SpaHandler, directory=str(static_dir))
    server = http.server.ThreadingHTTPServer(
        (FRONTEND_HOST, FRONTEND_PORT),
        handler,
    )
    thread = threading.Thread(
        target=server.serve_forever,
        name="nexyra-frontend",
        daemon=True,
    )
    thread.start()
    return server


def start_backend(app):
    import uvicorn

    config = uvicorn.Config(
        app,
        host=API_HOST,
        port=API_PORT,
        log_level="info",
        access_log=False,
        log_config=None,
        use_colors=False,
    )
    server = uvicorn.Server(config)
    server.install_signal_handlers = lambda: None
    thread = threading.Thread(
        target=server.run,
        name="nexyra-api",
        daemon=True,
    )
    thread.start()
    return server, thread


def open_first_access_file(path: Path) -> None:
    if os.name != "nt":
        return
    try:
        os.startfile(path)  # type: ignore[attr-defined]
    except OSError:
        logging.exception("Não foi possível abrir o arquivo de primeiro acesso")
        native_message(
            APP_NAME,
            f"As credenciais iniciais foram gravadas em:\n{path}",
            error=False,
        )


def run_desktop_window(frontend_url: str, data_dir: Path) -> None:
    try:
        import webview
    except ImportError as exc:
        raise RuntimeError(
            "O componente desktop (pywebview) não foi incluído no build."
        ) from exc

    webview.create_window(
        APP_NAME,
        frontend_url,
        width=WINDOW_WIDTH,
        height=WINDOW_HEIGHT,
        min_size=(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT),
        resizable=True,
        text_select=True,
        background_color="#0b1020",
    )

    try:
        webview.start(
            gui="edgechromium",
            debug=False,
            private_mode=False,
            storage_path=str(data_dir / "webview"),
        )
    except Exception as exc:
        raise RuntimeError(
            "Não foi possível iniciar a janela do Nexyra CRM. "
            "Verifique se o Microsoft Edge WebView2 Runtime está instalado."
        ) from exc


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Nexyra CRM Desktop")
    parser.add_argument("--smoke-test", action="store_true")
    parser.add_argument("--browser-fallback", action="store_true")
    parser.add_argument("--data-dir", type=Path, default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = resource_root()
    data_dir = (args.data_dir or default_data_dir()).resolve()
    ensure_runtime_environment(data_dir)
    configure_logging(data_dir)

    logging.info("Inicializando %s Desktop", APP_NAME)
    logging.info("Dados locais: %s", data_dir)

    try:
        run_migrations(root)
        first_access_path = ensure_first_access(data_dir)
        app = import_application()
    except Exception as exc:
        logging.exception("Falha durante inicialização/migrations")
        native_message(
            APP_NAME,
            f"O Nexyra CRM não conseguiu inicializar.\n\n{exc}\n\n"
            f"Consulte o log em:\n{data_dir / 'logs' / 'launcher.log'}",
            error=True,
        )
        return 1

    if args.smoke_test:
        logging.info("Smoke test do pacote concluído com sucesso.")
        return 0

    frontend_url = f"http://{FRONTEND_HOST}:{FRONTEND_PORT}"
    api_health_url = f"http://{API_HOST}:{API_PORT}/api/v1/health"

    if not port_is_free(API_HOST, API_PORT):
        if url_is_ready(api_health_url) and url_is_ready(frontend_url):
            native_message(APP_NAME, "O Nexyra CRM já está em execução.")
            return 0
        native_message(
            APP_NAME,
            f"A porta local {API_PORT} já está sendo usada por outro programa.",
            error=True,
        )
        return 2

    if not port_is_free(FRONTEND_HOST, FRONTEND_PORT):
        native_message(
            APP_NAME,
            f"A porta local {FRONTEND_PORT} já está sendo usada por outro programa.",
            error=True,
        )
        return 2

    static_dir = frontend_static_dir(root)
    frontend_server = None
    backend_server = None
    backend_thread = None

    try:
        frontend_server = start_frontend(static_dir)
        backend_server, backend_thread = start_backend(app)

        if not wait_for_url(api_health_url):
            raise RuntimeError("A API não respondeu dentro do tempo esperado.")
        if not wait_for_url(frontend_url):
            raise RuntimeError("A interface não respondeu dentro do tempo esperado.")

        logging.info("Nexyra CRM Desktop disponível em %s", frontend_url)

        if first_access_path is not None:
            threading.Timer(
                1.2,
                open_first_access_file,
                args=(first_access_path,),
            ).start()

        if args.browser_fallback:
            webbrowser.open(frontend_url)
            while backend_thread.is_alive():
                time.sleep(0.5)
        else:
            run_desktop_window(frontend_url, data_dir)

    except KeyboardInterrupt:
        logging.info("Encerramento solicitado pelo usuário")
    except Exception as exc:
        logging.exception("Falha ao iniciar o Nexyra CRM Desktop")
        native_message(
            APP_NAME,
            f"Não foi possível abrir o Nexyra CRM.\n\n{exc}\n\n"
            f"Log: {data_dir / 'logs' / 'launcher.log'}",
            error=True,
        )
        return 3
    finally:
        if backend_server is not None:
            backend_server.should_exit = True
        if frontend_server is not None:
            frontend_server.shutdown()
            frontend_server.server_close()
        if backend_thread is not None:
            backend_thread.join(timeout=5)

    logging.info("Nexyra CRM Desktop encerrado.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
