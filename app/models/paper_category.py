from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.paper import Paper
    from app.models.paper_week import PaperWeek


class PaperCategory(Base):
    __tablename__ = "paper_categories"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        unique=True,
    )

    slug: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
        unique=True,
        index=True,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    is_active: Mapped[bool] = mapped_column(
        default=True,
        nullable=False,
    )

    display_order: Mapped[int] = mapped_column(
        Integer,
        default=0,
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

    # --------------------------------------------------------
    # PERMANENT PAPERS
    # --------------------------------------------------------

    papers: Mapped[list["Paper"]] = relationship(
        "Paper",
        back_populates="category",
        cascade="all, delete-orphan",
    )

    # --------------------------------------------------------
    # WEEKS
    # --------------------------------------------------------

    weeks: Mapped[list["PaperWeek"]] = relationship(
        "PaperWeek",
        back_populates="category",
        cascade="all, delete-orphan",
        order_by="PaperWeek.year.desc(), PaperWeek.week_number.desc()",
    )