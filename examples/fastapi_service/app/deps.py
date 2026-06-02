# Re-export public dependencies consumed by route modules.
from fastapi_service.core.deps import CurrentUser as CurrentUser
from fastapi_service.core.engine_sync import SessionDep as SessionDep
