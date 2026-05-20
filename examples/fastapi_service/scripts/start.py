"""Container entrypoint: migrate DB, then start the server."""

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
    alembic_ini = "/opt/fastapi_service/alembic.ini"
    versions_dir = Path("/opt/shared_migrations/m8_app/versions")

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
                "Initial m8 migration",
            ]
        )

    print("Initialising DB...")
    _run([sys.executable, "-m", "fastapi_service.fastapi_pre_start"])

    print("Running migrations...")
    _run([sys.executable, "-m", "alembic", "-c", alembic_ini, "upgrade", "head"])

    # Replace the current process so the server receives signals directly.
    if os.environ.get("VSCODE_DEBUG") == "true":
        print("Starting fastapi_service under VS Code debugpy...")
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
                "fastapi_service.main:app",
                "--host",
                "0.0.0.0",
                "--port",
                "8000",
                "--reload",
            ],
        )
    else:
        os.execvp(
            "uvicorn",
            [
                "uvicorn",
                "fastapi_service.main:app",
                "--host",
                "0.0.0.0",
                "--port",
                "8000",
            ],
        )


if __name__ == "__main__":
    main()
