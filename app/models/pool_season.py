from datetime import datetime, time

from sqlalchemy import Boolean, DateTime, Integer, String, Time, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class PoolSeason(Base):
    __tablename__ = "pool_seasons"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    name: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
    )

    slug: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
        index=True,
    )

    # Python weekday:
    # Monday = 1
    # Tuesday = 2
    # Wednesday = 3
    # Thursday = 4
    # Friday = 5
    # Saturday = 6
    # Sunday = 7
    
    # Weekday convention used by the API:
    # Monday = 1, Tuesday = 2, ..., Sunday = 7.
    closing_weekday: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=6,
    )


    closing_time: Mapped[time] = mapped_column(
        Time,
        nullable=False,
        default=time(12, 0),
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
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

    pool_weeks = relationship(
        "PoolWeek",
        back_populates="season",
        cascade="all, delete-orphan",
        order_by="PoolWeek.year, PoolWeek.week_number",
    )

    free_games = relationship(
        "FreeGamePost",
        back_populates="season",
    )