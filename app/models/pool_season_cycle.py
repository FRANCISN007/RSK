
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class PoolSeasonCycle(Base):
    __tablename__ = "pool_season_cycles"

    __table_args__ = (
        UniqueConstraint(
            "name",
            name="uq_pool_season_cycle_name",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    # Example: 2026/2027
    name: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    english_season_id: Mapped[int] = mapped_column(
        ForeignKey("pool_seasons.id", ondelete="RESTRICT"),
        nullable=False,
    )

    aussie_season_id: Mapped[int] = mapped_column(
        ForeignKey("pool_seasons.id", ondelete="RESTRICT"),
        nullable=False,
    )

    # These are inclusive calendar dates during which
    # each season's weekly schedule is generated.
    english_start_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )

    english_end_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )

    aussie_start_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )

    aussie_end_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
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

    english_season = relationship(
        "PoolSeason",
        foreign_keys=[english_season_id],
    )

    aussie_season = relationship(
        "PoolSeason",
        foreign_keys=[aussie_season_id],
    )

    pool_weeks = relationship(
        "PoolWeek",
        back_populates="cycle",
        order_by="PoolWeek.week_number",
    )


