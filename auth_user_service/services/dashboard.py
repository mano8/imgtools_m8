"""
Dashboard Controller
"""
from datetime import datetime, timedelta
from sqlalchemy import case, and_
from sqlmodel import (
    Session,
    literal_column,
    select,
    func,
    union_all
)
from auth_sdk_m8.controllers.base import BaseController
from auth_user_service.services.users import UserController
from auth_user_service.core.deps import CurrentUser
from auth_user_service.schemas.dashboard import (
    RangeActivityType,
    UsersActivity
)
from auth_user_service.db_models.users import (
    User
)
# pylint: disable=broad-exception-caught


class DashboardController:
    """
    Dashboard Controller
    """
    @staticmethod
    def get_range_activity(
        time_range: RangeActivityType
    ) -> tuple[int, int]:
        """
        Calculate the start and end datetime for a given time range.
        Args:
            time_range (RangeActivityType):
            The type of time range to calculate.
                It can be one of the following:
                - RangeActivityType.HOUR: The current hour.
                - RangeActivityType.DAY: The current day.
                - RangeActivityType.MONTH: The current month.
                - RangeActivityType.YEAR: The current year.
        Returns:
            tuple[Optional[int], Optional[int]]:
                A tuple containing the start and end datetime objects
                for the specified time range.
        Raises:
            ValueError: If an invalid time_range is provided.
        """
        now = datetime.now()
        if time_range == RangeActivityType.HOUR:
            start = now.replace(minute=0, second=0, microsecond=0)
            end = start + timedelta(hours=1)
        elif time_range == RangeActivityType.DAY:
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + timedelta(days=1)
        elif time_range == RangeActivityType.MONTH:
            start = now.replace(
                day=1, hour=0, minute=0,
                second=0, microsecond=0
            )
            if start.month == 12:
                end = start.replace(year=start.year+1, month=1)
            else:
                end = start.replace(month=start.month+1)
        elif time_range == RangeActivityType.YEAR:
            start = now.replace(
                month=1, day=1, hour=0, minute=0, second=0,
                microsecond=0
            )
            end = start.replace(year=start.year+1)
        else:
            raise ValueError(
                "Invalid time_range provided. "
                "Use 'hour', 'day', 'month', or 'year'."
            )
        return start, end

    @staticmethod
    def get_updates_count_by_model(
        *,
        session: Session,
        current_user: CurrentUser,
        time_range: RangeActivityType
    ) -> dict[str, int]:
        """
        Count the number of updates per model within the given time range.
        """
        start, end = DashboardController.get_range_activity(time_range)

        models: list[tuple[type, str]] = [
            (User, "User")
        ]

        subqueries = []
        for model, model_name in models:
            query = (
                select(literal_column(f"'{model_name}'").label("model"))
                .select_from(model)
                .where(model.updated_at >= start, model.updated_at < end)
            )
            if not current_user.is_superuser:
                if model_name == 'User':
                    query = query.where(model.id == current_user.id)
                else:  # pragma: no cover
                    query = query.where(model.owner_id == current_user.id)
            subqueries.append(query)

        union_subq = union_all(*subqueries).subquery()

        stmt = (
            select(
                union_subq.c.model,
                func.count().label("updates")  # pylint: disable=not-callable
            )
            .group_by(union_subq.c.model)
        )

        results = session.exec(stmt).all()
        return [{"model": item[0], "value": item[1]} for item in results]

    @staticmethod
    def get_activity_count_by_model(
        *,
        session: Session,
        current_user: CurrentUser,
        time_range: RangeActivityType,
        is_current: bool = False
    ) -> list[dict[str, int]]:
        """
        Count updated and added rows per model within the given time range.
        """
        start, end = DashboardController.get_range_activity(time_range)

        models = [
            (User, "User"),
        ]
        result = {
            'max': 0,
            'min': 0,
            'activity': []
        }
        for model, model_name in models:
            stmt = select(
                func.sum(
                    case(
                        (
                            and_(
                                model.updated_at >= start,
                                model.updated_at < end
                            ),
                            1
                        ),
                        else_=0
                    )
                ).label("updated"),
                func.sum(
                    case(
                        (
                            and_(
                                model.created_at >= start,
                                model.created_at < end
                            ),
                            1
                        ),
                        else_=0
                    )
                ).label("added")
            ).select_from(model)
            if not current_user.is_superuser or is_current is True:
                if model_name == 'User':
                    stmt = stmt.where(model.id == current_user.id)
                else:  # pragma: no cover
                    stmt = stmt.where(model.owner_id == current_user.id)
            row = session.exec(stmt).first()
            updated_count = row.updated\
                if row and row.updated is not None else 0
            added_count = row.added if row and row.added is not None else 0
            result['activity'].append({
                "model": model_name,
                "updated": updated_count,
                "added": added_count
            })
            result['min'] = min(result['min'], updated_count, added_count)
            result['max'] = max(result['max'], updated_count, added_count)
        return result

    @staticmethod
    def get_dash_users_stats(
        session: Session,
        current_user: CurrentUser,
        time_range: RangeActivityType,
        is_current: bool = False
    ) -> UsersActivity:
        """
        Retrieves dashboard user statistics.
        """
        try:
            nb_users, activity = 0, []
            if current_user.is_superuser:
                nb_users = UserController.count_users(
                    session=session
                )

            activity = DashboardController.get_activity_count_by_model(
                session=session,
                current_user=current_user,
                time_range=time_range,
                is_current=is_current
            )
            return UsersActivity(
                nb_users=nb_users,
                activity=activity
            )
        except Exception as ex:
            return BaseController.handle_exception(
                ex=ex,
                session=session
            )
