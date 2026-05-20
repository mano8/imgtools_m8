"""Container entrypoint: migrate DB, seed data, then start the server."""

import os
import signal
import sys
from pathlib import Path
from subprocess import Popen
from subprocess import run as _sp_run


def _run(cmd: list[str]) -> None:
    """Run *cmd*, exit with its return code on failure."""
    result = _sp_run(cmd)
    if result.returncode != 0:
        sys.exit(result.returncode)


def _serve(cmd: list[str]) -> None:
    """Start the server and forward SIGTERM/SIGINT for graceful shutdown."""
    proc = Popen(cmd)

    def _forward(signum: int, _frame: object) -> None:
        proc.send_signal(signum)

    signal.signal(signal.SIGTERM, _forward)
    signal.signal(signal.SIGINT, _forward)
    sys.exit(proc.wait())


def main() -> None:
    """Prepare the database and start the ASGI server."""
    alembic_ini = "/opt/auth_user_service/alembic.ini"
    versions_dir = Path("/opt/shared_migrations/auth_user/versions")

    if not any(versions_dir.glob("*.py")):
        print("Generating initial Alembic migration...")
        _run(
            [
                sys.executable, "-m", "alembic",
                "-c", alembic_ini,
                "revision", "--autogenerate", "-m", "Initial auth migration",
            ]
        )
    else:
        print("Migrations already exist, skipping generation.")

    print("Initialising DB...")
    _run([sys.executable, "-m", "auth_user_service.scripts.fastapi_pre_start"])

    print("Running migrations...")
    _run([sys.executable, "-m", "alembic", "-c", alembic_ini, "upgrade", "head"])

    print("Creating initial data...")
    _run([sys.executable, "-m", "auth_user_service.scripts.initial_data"])

    trusted_ips = os.environ.get("TRUSTED_PROXY_IPS", "172.16.0.0/12")
    if os.environ.get("VSCODE_DEBUG") == "true":
        print("Starting auth_user_service under VS Code debugpy...")
        _serve(
            [
                sys.executable, "-m", "debugpy",
                "--listen", "0.0.0.0:5678",
                "--wait-for-client",
                "-m", "uvicorn", "auth_user_service.main:app",
                "--host", "0.0.0.0",  # nosec B104
                "--port", "8000", "--reload",
                "--proxy-headers",
                f"--forwarded-allow-ips={trusted_ips}",
            ]
        )
    else:
        _serve(
            [
                "uvicorn", "auth_user_service.main:app",
                "--host", "0.0.0.0",  # nosec B104
                "--port", "8000",
                "--proxy-headers",
                f"--forwarded-allow-ips={trusted_ips}",
            ]
        )


if __name__ == "__main__":
    main()
