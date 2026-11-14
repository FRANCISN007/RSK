
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.user import User



class DiscussionCategory(Base):
    __tablename__ = "discussion_categories"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, index=True
    )

    name: Mapped[str] = mapped_column(
        String(100), nullable=False, unique=True
    )

    slug: Mapped[str] = mapped_column(
        String(120), nullable=False, unique=True, index=True
    )

    description: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )

    access_level: Mapped[str] = mapped_column(
        String(20), nullable=False, default="public"
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )

    display_order: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    topics: Mapped[list["DiscussionTopic"]] = relationship(
        back_populates="category"
    )

    __table_args__ = (
        CheckConstraint(
            "access_level IN ('public', 'members')",
            name="ck_discussion_category_access_level",
        ),
    )


class DiscussionTopic(Base):
    __tablename__ = "discussion_topics"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, index=True
    )

    category_id: Mapped[int] = mapped_column(
        ForeignKey("discussion_categories.id"),
        nullable=False,
        index=True,
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    title: Mapped[str] = mapped_column(
        String(250), nullable=False
    )

    content: Mapped[str] = mapped_column(
        Text, nullable=False
    )

    is_pinned: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )

    is_locked: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )

    is_hidden: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )

    view_count: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
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

    category: Mapped["DiscussionCategory"] = relationship(
        back_populates="topics"
    )

    user: Mapped["User"] = relationship("User")

    comments: Mapped[list["DiscussionComment"]] = relationship(
        back_populates="topic",
        cascade="all, delete-orphan",
    )


class DiscussionComment(Base):
    __tablename__ = "discussion_comments"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, index=True
    )

    topic_id: Mapped[int] = mapped_column(
        ForeignKey("discussion_topics.id"),
        nullable=False,
        index=True,
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("discussion_comments.id"),
        nullable=True,
        index=True,
    )

    content: Mapped[str] = mapped_column(
        Text, nullable=False
    )

    is_hidden: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
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

    topic: Mapped["DiscussionTopic"] = relationship(
        back_populates="comments"
    )

    user: Mapped["User"] = relationship("User")

    parent: Mapped["DiscussionComment | None"] = relationship(
        "DiscussionComment",
        remote_side="DiscussionComment.id",
        back_populates="replies",
    )

    replies: Mapped[list["DiscussionComment"]] = relationship(
        "DiscussionComment",
        back_populates="parent",
    )


class DiscussionLike(Base):
    __tablename__ = "discussion_likes"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, index=True
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    topic_id: Mapped[int | None] = mapped_column(
        ForeignKey("discussion_topics.id"),
        nullable=True,
        index=True,
    )

    comment_id: Mapped[int | None] = mapped_column(
        ForeignKey("discussion_comments.id"),
        nullable=True,
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint(
            """
            (topic_id IS NOT NULL AND comment_id IS NULL)
            OR
            (topic_id IS NULL AND comment_id IS NOT NULL)
            """,
            name="ck_discussion_like_single_target",
        ),
        UniqueConstraint(
            "user_id", "topic_id",
            name="uq_discussion_like_user_topic",
        ),
        UniqueConstraint(
            "user_id", "comment_id",
            name="uq_discussion_like_user_comment",
        ),
    )


class DiscussionReport(Base):
    __tablename__ = "discussion_reports"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, index=True
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    topic_id: Mapped[int | None] = mapped_column(
        ForeignKey("discussion_topics.id"),
        nullable=True,
        index=True,
    )

    comment_id: Mapped[int | None] = mapped_column(
        ForeignKey("discussion_comments.id"),
        nullable=True,
        index=True,
    )

    reason: Mapped[str] = mapped_column(
        String(100), nullable=False
    )

    description: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )

    status: Mapped[str] = mapped_column(
        String(20), default="pending", nullable=False
    )

    reviewed_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        CheckConstraint(
            """
            (topic_id IS NOT NULL AND comment_id IS NULL)
            OR
            (topic_id IS NULL AND comment_id IS NOT NULL)
            """,
            name="ck_discussion_report_single_target",
        ),
        CheckConstraint(
            "status IN ('pending', 'reviewed', 'dismissed', 'actioned')",
            name="ck_discussion_report_status",
        ),
    )


class DiscussionNotification(Base):
    __tablename__ = "discussion_notifications"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, index=True
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    actor_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"),
        nullable=True,
    )

    topic_id: Mapped[int | None] = mapped_column(
        ForeignKey("discussion_topics.id"),
        nullable=True,
    )

    comment_id: Mapped[int | None] = mapped_column(
        ForeignKey("discussion_comments.id"),
        nullable=True,
    )

    notification_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )

    message: Mapped[str] = mapped_column(
        String(500), nullable=False
    )

    is_read: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
