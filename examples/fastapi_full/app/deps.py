"""Re-export public dependencies consumed by route modules."""

__all__ = ["CurrentUser", "SessionDep"]

from fastapi_full.core.deps import CurrentUser as CurrentUser
from fastapi_full.core.engine_sync import SessionDep as SessionDep
