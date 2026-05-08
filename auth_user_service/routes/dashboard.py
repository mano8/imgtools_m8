"""
DashBoard routes
"""

from fastapi import APIRouter
from auth_sdk_m8.controllers.base import BaseController
from auth_user_service.core.deps import CurrentUser, SessionDep
from auth_user_service.services.dashboard import DashboardController
from auth_user_service.schemas.dashboard import RangeActivityType, UsersActivity

router = APIRouter(prefix="/dashboard", tags=["dashboard"])
# pylint: disable=broad-exception-caught, unused-argument


@router.get(
    "/users/activity/",
    response_model=UsersActivity,
    responses=BaseController.get_error_responses(),
)
def get_dash_users_stats(
    session: SessionDep, current_user: CurrentUser
) -> UsersActivity:
    """Get phpfina files list from source."""
    return DashboardController.get_dash_users_stats(
        session=session, current_user=current_user, time_range=RangeActivityType.MONTH
    )


@router.get(
    "/users/activity/current/",
    response_model=UsersActivity,
    responses=BaseController.get_error_responses(),
)
def get_dash_current_user_stats(
    session: SessionDep, current_user: CurrentUser
) -> UsersActivity:
    """Get phpfina files list from source."""
    return DashboardController.get_dash_users_stats(
        session=session,
        current_user=current_user,
        time_range=RangeActivityType.MONTH,
        is_current=True,
    )
