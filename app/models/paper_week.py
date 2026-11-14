from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.paper_category import PaperCategory
    from app.models.week_paper import EditionPaper


class PaperWeek(Base):
    __tablename__ = "paper_editions"

    __table_args__ = (
        UniqueConstraint(
            "category_id",
            "year",
            "week_number",
            name="uq_category_edition_week",
        ),
        CheckConstraint(
            "week_number >= 1 AND week_number <= 53",
            name="ck_paper_edition_week_number",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    # --------------------------------------------------------
    # CATEGORY
    # --------------------------------------------------------

    category_id: Mapped[int] = mapped_column(
        ForeignKey("paper_categories.id"),
        nullable=False,
        index=True,
    )

    # --------------------------------------------------------
    # WEEK
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # STATUS
    # --------------------------------------------------------

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="draft",
        index=True,
    )

    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # --------------------------------------------------------
    # TIMESTAMPS
    # --------------------------------------------------------

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
    # CATEGORY RELATIONSHIP
    # --------------------------------------------------------

    category: Mapped["PaperCategory"] = relationship(
        "PaperCategory",
        back_populates="weeks",
    )

    # --------------------------------------------------------
    # PAPERS ATTACHED TO THIS WEEK
    # --------------------------------------------------------

    week_papers: Mapped[list["EditionPaper"]] = relationship(
        "EditionPaper",
        back_populates="edition",
        cascade="all, delete-orphan",
        order_by="EditionPaper.display_order",
    )


    