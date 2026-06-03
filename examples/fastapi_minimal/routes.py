"""API routes for the minimal example."""

from fastapi import APIRouter

from .core.deps import CurrentUser

router = APIRouter(prefix="/hello", tags=["hello"])


@router.get("/")
def hello(current_user: CurrentUser) -> dict:  # type: ignore[valid-type]
    """Return a greeting for the authenticated user."""
    return {"hello": current_user.email}
