from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.dependencies.auth import require_admin
from app.models.pool_season import PoolSeason
from app.models.pool_week import PoolWeek
from app.models.user import User
from app.schemas.pool_week import (
    PoolWeekCreate,
    PoolWeekResponse,
)


router = APIRouter(
    prefix="/admin/pool-weeks",
    tags=["Admin Pool Weeks"],
)


POOL_TIMEZONE = ZoneInfo("Africa/Lagos")


def calculate_closing_datetime(year, week_number, closing_weekday, closing_time):
    monday = datetime.fromisocalendar(year, week_number, 1).date()

    # Our system: Monday=1 ... Sunday=7
    # Python:     Monday=0 ... Sunday=6
    python_weekday = closing_weekday - 1

    closing_date = monday + timedelta(days=python_weekday)

    closing_local = datetime.combine(
        closing_date,
        closing_time,
    ).replace(tzinfo=POOL_TIMEZONE)

    return closing_local.astimezone(timezone.utc)




@router.post(
    "",
    response_model=PoolWeekResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_pool_week(
    data: PoolWeekCreate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    season = db.get(
        PoolSeason,
        data.season_id,
    )

    if season is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pool season not found.",
        )

    if not season.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This pool season is inactive.",
        )

    existing = db.scalar(
        select(PoolWeek).where(
            PoolWeek.season_id == data.season_id,
            PoolWeek.year == data.year,
            PoolWeek.week_number == data.week_number,
        )
    )

    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This pool week already exists.",
        )

    closes_at = calculate_closing_datetime(
        year=data.year,
        week_number=data.week_number,
        closing_weekday=season.closing_weekday,
        closing_time=season.closing_time,
    )

    pool_week = PoolWeek(
        season_id=season.id,
        year=data.year,
        week_number=data.week_number,
        closes_at=closes_at,
    )

    db.add(pool_week)
    db.commit()
    db.refresh(pool_week)

    return pool_week


@router.get(
    "",
    response_model=list[PoolWeekResponse],
)
def get_pool_weeks(
    season_id: int | None = None,
    year: int | None = None,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    query = (
        select(PoolWeek)
        .options(
            joinedload(PoolWeek.season),
        )
    )

    if season_id is not None:
        query = query.where(
            PoolWeek.season_id == season_id
        )

    if year is not None:
        query = query.where(
            PoolWeek.year == year
        )

    query = query.order_by(
        PoolWeek.year.desc(),
        PoolWeek.week_number.desc(),
    )

    weeks = db.scalars(query).unique().all()

    return weeks


@router.get(
    "/{pool_week_id}",
    response_model=PoolWeekResponse,
)
def get_pool_week(
    pool_week_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    pool_week = db.scalar(
        select(PoolWeek)
        .options(
            joinedload(PoolWeek.season),
        )
        .where(
            PoolWeek.id == pool_week_id,
        )
    )

    if pool_week is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pool week not found.",
        )

    return pool_week


@router.delete(
    "/{pool_week_id}",
)
def delete_pool_week(
    pool_week_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    pool_week = db.get(
        PoolWeek,
        pool_week_id,
    )

    if pool_week is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pool week not found.",
        )

    if pool_week.free_games:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "This pool week cannot be deleted because "
                "games are already attached to it."
            ),
        )

    db.delete(pool_week)
    db.commit()

    return {
        "message": "Pool week deleted successfully.",
    }