from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class FreeGamePost(Base):
    __tablename__ = "free_game_posts"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    season_id: Mapped[int] = mapped_column(
        ForeignKey("pool_seasons.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    pool_week_id: Mapped[int] = mapped_column(
        ForeignKey("pool_weeks.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    title: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )

    # Keep this for compatibility with your current API/database.
    # The actual week relationship is now pool_week_id.
    week: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    game_data: Mapped[dict | list | None] = mapped_column(
        JSON,
        nullable=True,
    )

    is_published: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    user = relationship(
        "User",
        backref="free_game_posts",
    )

    season = relationship(
        "PoolSeason",
        back_populates="free_games",
    )

    pool_week = relationship(
        "PoolWeek",
        back_populates="free_games",
    )