from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

from app.models.paper_category import PaperCategory
from app.models.week_paper import EditionPaper
from app.models.paper_page import PaperPage


class Paper(Base):
    __tablename__ = "papers"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    category_id: Mapped[int] = mapped_column(
        ForeignKey("paper_categories.id"),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    slug: Mapped[str] = mapped_column(
        String(180),
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
    # Category
    # --------------------------------------------------------

    category: Mapped["PaperCategory"] = relationship(
        "PaperCategory",
        back_populates="papers",
    )

    # --------------------------------------------------------
    # Weeks
    #
    # This is the permanent Paper -> Week relationship
    # through EditionPaper.
    # --------------------------------------------------------

    edition_papers: Mapped[list["EditionPaper"]] = relationship(
        "EditionPaper",
        back_populates="paper",
        cascade="all, delete-orphan",
        order_by="EditionPaper.display_order",
    )

    # --------------------------------------------------------
    # Pages
    #
    # Pages belong directly to the permanent Paper.
    # Week is NOT involved here.
    # --------------------------------------------------------

    pages: Mapped[list["PaperPage"]] = relationship(
        "PaperPage",
        back_populates="paper",
        cascade="all, delete-orphan",
        order_by="PaperPage.page_number",
    )