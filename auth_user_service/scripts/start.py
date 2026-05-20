"""Container entrypoint: migrate DB, seed data, then start the server."""

import os
import sys
from pathlib import Path
from subprocess import run as _sp_run


def _run(cmd: list[str]) -> None:
    """Run *cmd*, exit with its return code on failure."""
    result = _sp_run(cmd)
    if result.returncode != 0:
        sys.exit(result.returncode)


def main() -> None:
    """Prepare the database and start the ASGI server."""
    alembic_ini = "/opt/auth_user_service/alembic.ini"
    versions_dir = Path("/opt/shared_migrations/auth_user/versions")

    # Generate the initial migration when the versions directory is empty.
    if not any(versions_dir.glob("*.py")):
        print("Generating initial Alembic migration...")
        _run(
            [
                sys.executable,
                "-m",
                "alembic",
                "-c",
                alembic_ini,
                "revision",
                "--autogenerate",
                "-m",
                "Initial auth migration",
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

    # Replace the current process so the server receives signals directly.
    trusted_ips = os.environ.get("TRUSTED_PROXY_IPS", "172.16.0.0/12")
    if os.environ.get("VSCODE_DEBUG") == "true":
        print("Starting auth_user_service under VS Code debugpy...")
        os.execvp(
            sys.executable,
            [
                sys.executable,
                "-m",
                "debugpy",
                "--listen",
                "0.0.0.0:5678",
                "--wait-for-client",
                "-m",
                "uvicorn",
                "auth_user_service.main:app",
                "--host",
                "0.0.0.0",
                "--port",
                "8000",
                "--reload",
                "--proxy-headers",
                f"--forwarded-allow-ips={trusted_ips}",
            ],
        )
    else:
        os.execvp(
            "uvicorn",
            [
                "uvicorn",
                "auth_user_service.main:app",
                "--host",
                "0.0.0.0",
                "--port",
                "8000",
                "--proxy-headers",
                f"--forwarded-allow-ips={trusted_ips}",
            ],
        )


if __name__ == "__main__":
    main()
