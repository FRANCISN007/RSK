from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.dependencies.auth import get_current_user
from app.models.free_game import FreeGamePost
from app.models.pool_season import PoolSeason
from app.models.pool_week import PoolWeek
from app.models.user import User
from datetime import datetime, timezone
from app.schemas.free_game import (
    FreeGameCreate,
    FreeGameResponse,
    FreeGameUpdate,
)



router = APIRouter(
    prefix="/free-games",
    tags=["Free User Games"],
)


def is_pool_week_locked(closes_at) -> bool:
    """
    Return True when the pool week's closing time
    has been reached or passed.
    """

    now = datetime.now(timezone.utc)

    if closes_at.tzinfo is None:
        closes_at = closes_at.replace(tzinfo=timezone.utc)

    return now >= closes_at


def get_game_with_relationships(
    game_id: int,
    db: Session,
):
    return db.scalar(
        select(FreeGamePost)
        .options(
            joinedload(FreeGamePost.user),
            joinedload(FreeGamePost.season),
            joinedload(FreeGamePost.pool_week),
        )
        .where(
            FreeGamePost.id == game_id
        )
    )


def ensure_game_is_editable(
    game: FreeGamePost,
):
    """
    Prevent modification of a game after the PoolWeek
    closing time has passed.
    """

    if game.pool_week is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This game is not linked to a valid pool week.",
        )

    if is_pool_week_locked(
        game.pool_week.closes_at
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "This game is locked because the closing time "
                "for this pool week has passed."
            ),
        )


@router.post(
    "",
    response_model=FreeGameResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_free_game(
    data: FreeGameCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # ---------------------------------------------------------
    # Get selected season
    # ---------------------------------------------------------
    season = db.scalar(
        select(PoolSeason).where(
            PoolSeason.id == data.season_id,
            PoolSeason.is_active.is_(True),
        )
    )

    if season is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "Selected pool season was not found "
                "or is inactive."
            ),
        )

    # ---------------------------------------------------------
    # Get selected pool week
    # ---------------------------------------------------------
    pool_week = db.scalar(
        select(PoolWeek).where(
            PoolWeek.id == data.pool_week_id,
        )
    )

    if pool_week is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Selected pool week was not found.",
        )

    # ---------------------------------------------------------
    # Make sure the week belongs to the selected season
    # ---------------------------------------------------------
    if pool_week.season_id != season.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "The selected pool week does not belong "
                "to the selected season."
            ),
        )

    # ---------------------------------------------------------
    # Check weekly lock
    # ---------------------------------------------------------
    if is_pool_week_locked(
        pool_week.closes_at
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "This pool week is already closed. "
                "Games can no longer be posted for this week."
            ),
        )

    # ---------------------------------------------------------
    # Keep the old week field for compatibility.
    # PoolWeek is now authoritative.
    # ---------------------------------------------------------
    week_text = (
        f"Week {pool_week.week_number}, "
        f"{pool_week.year}"
    )

    game = FreeGamePost(
        user_id=current_user.id,
        season_id=season.id,
        pool_week_id=pool_week.id,
        title=data.title,
        week=week_text,
        description=data.description,
        game_data=data.game_data,
        is_published=True,
        is_active=True,
    )

    db.add(game)
    db.commit()
    db.refresh(game)

    # ---------------------------------------------------------
    # Reload with relationships required by response schema
    # ---------------------------------------------------------
    game = get_game_with_relationships(
        game.id,
        db,
    )

    return game


@router.get(
    "",
    response_model=list[FreeGameResponse],
)
def get_public_free_games(
    db: Session = Depends(get_db),
):
    games = db.scalars(
        select(FreeGamePost)
        .options(
            joinedload(FreeGamePost.user),
            joinedload(FreeGamePost.season),
            joinedload(FreeGamePost.pool_week),
        )
        .where(
            FreeGamePost.is_active.is_(True),
            FreeGamePost.is_published.is_(True),
        )
        .order_by(
            FreeGamePost.created_at.desc(),
        )
    ).unique().all()

    return games


@router.get(
    "/my",
    response_model=list[FreeGameResponse],
)
def get_my_free_games(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    games = db.scalars(
        select(FreeGamePost)
        .options(
            joinedload(FreeGamePost.user),
            joinedload(FreeGamePost.season),
            joinedload(FreeGamePost.pool_week),
        )
        .where(
            FreeGamePost.user_id == current_user.id,
            FreeGamePost.is_active.is_(True),
        )
        .order_by(
            FreeGamePost.created_at.desc(),
        )
    ).unique().all()

    return games


@router.get(
    "/{game_id}",
    response_model=FreeGameResponse,
)
def get_free_game(
    game_id: int,
    db: Session = Depends(get_db),
):
    game = db.scalar(
        select(FreeGamePost)
        .options(
            joinedload(FreeGamePost.user),
            joinedload(FreeGamePost.season),
            joinedload(FreeGamePost.pool_week),
        )
        .where(
            FreeGamePost.id == game_id,
            FreeGamePost.is_active.is_(True),
            FreeGamePost.is_published.is_(True),
        )
    )

    if game is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Free game not found.",
        )

    return game


@router.put(
    "/{game_id}",
    response_model=FreeGameResponse,
)
def update_free_game(
    game_id: int,
    data: FreeGameUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    game = db.scalar(
        select(FreeGamePost)
        .options(
            joinedload(FreeGamePost.pool_week),
        )
        .where(
            FreeGamePost.id == game_id,
            FreeGamePost.is_active.is_(True),
        )
    )

    if game is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Free game not found.",
        )

    # ---------------------------------------------------------
    # Only the owner can edit the game
    # ---------------------------------------------------------
    if game.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only edit your own games.",
        )

    # ---------------------------------------------------------
    # Check the actual PoolWeek closing time
    # ---------------------------------------------------------
    ensure_game_is_editable(game)

    # ---------------------------------------------------------
    # Update editable game content only.
    #
    # Season and PoolWeek cannot be changed after creation.
    # ---------------------------------------------------------
    if data.title is not None:
        game.title = data.title

    if data.description is not None:
        game.description = data.description

    if data.game_data is not None:
        game.game_data = data.game_data

    if data.is_published is not None:
        game.is_published = data.is_published

    db.commit()

    game = get_game_with_relationships(
        game.id,
        db,
    )

    return game


@router.delete(
    "/{game_id}",
)
def delete_free_game(
    game_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    game = db.scalar(
        select(FreeGamePost)
        .options(
            joinedload(FreeGamePost.pool_week),
        )
        .where(
            FreeGamePost.id == game_id,
            FreeGamePost.is_active.is_(True),
        )
    )

    if game is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Free game not found.",
        )

    # ---------------------------------------------------------
    # Only the owner can delete the game
    # ---------------------------------------------------------
    if game.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only delete your own games.",
        )

    # ---------------------------------------------------------
    # A game cannot be deleted after the PoolWeek closes.
    # ---------------------------------------------------------
    ensure_game_is_editable(game)

    # ---------------------------------------------------------
    # Soft delete
    # ---------------------------------------------------------
    game.is_active = False

    db.commit()

    return {
        "message": "Free game deleted successfully.",
    }