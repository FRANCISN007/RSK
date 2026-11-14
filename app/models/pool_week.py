
from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class PoolWeek(Base):
    __tablename__ = "pool_weeks"

    __table_args__ = (
        # Retain the existing constraint for legacy weeks.
        UniqueConstraint(
            "season_id",
            "year",
            "week_number",
            name="uq_pool_week_season_year_week",
        ),
        # A week number can appear only once in a cycle,
        # even when the season changes from English to Aussie.
        UniqueConstraint(
            "cycle_id",
            "week_number",
            name="uq_pool_week_cycle_week",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    # Nullable for existing weeks created before cycles existed.
    cycle_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "pool_season_cycles.id",
            ondelete="RESTRICT",
        ),
        nullable=True,
        index=True,
    )

    season_id: Mapped[int] = mapped_column(
        ForeignKey("pool_seasons.id", ondelete="CASCADE"),
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

    # The actual saved cutoff timestamp for this week.
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

    cycle = relationship(
        "PoolSeasonCycle",
        back_populates="pool_weeks",
    )

    season = relationship(
        "PoolSeason",
        back_populates="pool_weeks",
    )

    free_games = relationship(
        "FreeGamePost",
        back_populates="pool_week",
    )
