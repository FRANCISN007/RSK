from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.paper import Paper
    from app.models.paper_week import PaperWeek


class EditionPaper(Base):
    __tablename__ = "edition_papers"

    __table_args__ = (
        UniqueConstraint(
            "edition_id",
            "paper_id",
            name="uq_edition_paper",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    edition_id: Mapped[int] = mapped_column(
        ForeignKey("paper_editions.id"),
        nullable=False,
        index=True,
    )

    paper_id: Mapped[int] = mapped_column(
        ForeignKey("papers.id"),
        nullable=False,
        index=True,
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

    edition: Mapped["PaperWeek"] = relationship(
        "PaperWeek",
        back_populates="week_papers",
    )

    paper: Mapped["Paper"] = relationship(
        "Paper",
        back_populates="edition_papers",
    )