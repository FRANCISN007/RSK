from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import require_admin
from app.models.pool_season import PoolSeason
from app.models.user import User
from app.schemas.pool_season import (
    PoolSeasonCreate,
    PoolSeasonResponse,
    PoolSeasonUpdate,
)


router = APIRouter(
    prefix="/admin/pool-seasons",
    tags=["Admin Pool Seasons"],
)


@router.post(
    "",
    response_model=PoolSeasonResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_pool_season(
    data: PoolSeasonCreate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    existing = db.scalar(
        select(PoolSeason).where(
            (PoolSeason.name == data.name)
            | (PoolSeason.slug == data.slug)
        )
    )

    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A pool season with that name or slug already exists.",
        )

    season = PoolSeason(
        name=data.name,
        slug=data.slug,
        closing_weekday=data.closing_weekday,
        closing_time=data.closing_time,
        is_active=data.is_active,
    )

    db.add(season)
    db.commit()
    db.refresh(season)

    return season


@router.get(
    "",
    response_model=list[PoolSeasonResponse],
)
def get_pool_seasons(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    seasons = db.scalars(
        select(PoolSeason)
        .order_by(PoolSeason.name)
    ).all()

    return seasons


@router.get(
    "/{season_id}",
    response_model=PoolSeasonResponse,
)
def get_pool_season(
    season_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    season = db.get(PoolSeason, season_id)

    if season is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pool season not found.",
        )

    return season


@router.put(
    "/{season_id}",
    response_model=PoolSeasonResponse,
)
def update_pool_season(
    season_id: int,
    data: PoolSeasonUpdate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    season = db.get(PoolSeason, season_id)

    if season is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pool season not found.",
        )

    if data.name is not None and data.name != season.name:
        existing = db.scalar(
            select(PoolSeason).where(
                PoolSeason.name == data.name,
                PoolSeason.id != season_id,
            )
        )

        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Another pool season already uses that name.",
            )

        season.name = data.name

    if data.slug is not None and data.slug != season.slug:
        existing = db.scalar(
            select(PoolSeason).where(
                PoolSeason.slug == data.slug,
                PoolSeason.id != season_id,
            )
        )

        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Another pool season already uses that slug.",
            )

        season.slug = data.slug

    if data.closing_weekday is not None:
        season.closing_weekday = data.closing_weekday

    if data.closing_time is not None:
        season.closing_time = data.closing_time

    if data.is_active is not None:
        season.is_active = data.is_active

    db.commit()
    db.refresh(season)

    return season


@router.delete(
    "/{season_id}",
)
def delete_pool_season(
    season_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    season = db.get(PoolSeason, season_id)

    if season is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pool season not found.",
        )

    if season.pool_weeks:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "This season cannot be deleted because pool weeks "
                "already exist for it."
            ),
        )

    db.delete(season)
    db.commit()

    return {
        "message": "Pool season deleted successfully.",
    }