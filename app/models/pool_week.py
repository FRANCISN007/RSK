from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class PoolWeek(Base):
    __tablename__ = "pool_weeks"

    __table_args__ = (
        UniqueConstraint(
            "season_id",
            "year",
            "week_number",
            name="uq_pool_week_season_year_week",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    season_id: Mapped[int] = mapped_column(
        ForeignKey(
            "pool_seasons.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    year: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True,
    )

    week_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True,
    )

    # The actual moment this particular pool week closes.
    # This is calculated from the season's closing rule
    # when the week is created.
    closes_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
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

    season = relationship(
        "PoolSeason",
        back_populates="pool_weeks",
    )

    free_games = relationship(
        "FreeGamePost",
        back_populates="pool_week",
    )