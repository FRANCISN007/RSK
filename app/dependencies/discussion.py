
from datetime import datetime, timezone

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.models.membership import Membership
from app.models.discussion import (
    DiscussionCategory,
    DiscussionTopic,
    DiscussionComment,
)


# =========================================================
# ACTIVE MEMBERSHIP
# =========================================================

def find_active_membership(
    db: Session,
    user_id: int,
) -> Membership | None:

    now = datetime.now(timezone.utc)

    return db.scalar(
        select(Membership)
        .where(
            Membership.user_id == user_id,
            Membership.status == "active",
            Membership.end_date > now,
        )
        .order_by(Membership.end_date.desc())
    )


def get_active_membership(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Membership | None:

    return find_active_membership(db, current_user.id)


def require_active_member(
    membership: Membership | None = Depends(get_active_membership),
) -> Membership:

    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="An active membership is required.",
        )

    return membership


# =========================================================
# DISCUSSION CATEGORY ACCESS
# =========================================================

def check_category_access(
    category: DiscussionCategory,
    current_user: User | None,
    db: Session,
) -> None:

    if not category.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Discussion category not found.",
        )

    if category.access_level == "public":
        return

    if current_user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Please log in to access this discussion.",
        )

    if current_user.is_admin:
        return

    membership = find_active_membership(
        db,
        current_user.id,
    )

    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="An active membership is required to access this discussion.",
        )


# =========================================================
# TOPIC OWNER OR ADMIN
# =========================================================

def require_topic_owner_or_admin(
    topic_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DiscussionTopic:

    topic = db.scalar(
        select(DiscussionTopic).where(
            DiscussionTopic.id == topic_id
        )
    )

    if topic is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Discussion topic not found.",
        )

    if (
        topic.user_id != current_user.id
        and not current_user.is_admin
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not allowed to manage this discussion.",
        )

    return topic


# =========================================================
# COMMENT OWNER OR ADMIN
# =========================================================

def require_comment_owner_or_admin(
    comment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DiscussionComment:

    comment = db.scalar(
        select(DiscussionComment).where(
            DiscussionComment.id == comment_id
        )
    )

    if comment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Discussion comment not found.",
        )

    if (
        comment.user_id != current_user.id
        and not current_user.is_admin
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not allowed to manage this comment.",
        )

    return comment
