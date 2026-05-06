# fastapi_service/fastapi/api/deps.py
from fastapi_service.core.deps import (
    TokenDep,
    get_current_user,
    CurrentUser,
    UserRoleHelper
)
from fastapi_service.core.engine_sync import get_db, SessionDep
