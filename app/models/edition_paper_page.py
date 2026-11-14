
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
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
    from app.models.week_paper import EditionPaper


class EditionPaperPage(Base):
    __tablename__ = "edition_paper_pages"

    __table_args__ = (
        UniqueConstraint(
            "edition_paper_id",
            "page_number",
            name="uq_edition_paper_page_number",
        ),
        CheckConstraint(
            "page_number >= 1 AND page_number <= 4",
            name="ck_edition_paper_page_number",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    edition_paper_id: Mapped[int] = mapped_column(
        ForeignKey("edition_papers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    page_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    file_path: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    file_type: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    is_marked: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    marked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    edition_paper: Mapped["EditionPaper"] = relationship(
        "EditionPaper",
        back_populates="pages",
    )
