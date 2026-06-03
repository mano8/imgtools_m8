"""Build-once site for auth and database dependencies.

Import ``auth``, ``engine``, ``CurrentUser``, and ``SessionDep`` from here.
Never call ``build_auth_deps`` or ``create_db_engine`` a second time.
"""

from typing import Annotated

from fastapi import Depends
from sqlmodel import Session

from fastapi_m8 import AuthDeps, DbEngine, build_auth_deps, create_db_engine

from .config import settings

# Single instances shared across the entire process.
auth: AuthDeps = build_auth_deps(settings)
engine: DbEngine = create_db_engine(settings)

CurrentUser = auth.CurrentUser
get_current_user = auth.get_current_user
get_db = engine.session_dep
SessionDep = Annotated[Session, Depends(get_db)]
