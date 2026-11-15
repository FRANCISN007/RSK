
import re

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from datetime import datetime, timezone


from sqlalchemy import select, func, update, desc
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import IntegrityError


from app.database import get_db
from app.models.discussion import DiscussionCategory
from app.models.user import User
from app.schemas.discussion import (
    DiscussionCategoryCreate,
    DiscussionCategoryUpdate,
    DiscussionCategoryResponse,
)
from app.dependencies.auth import (
    get_optional_current_user,
)
from app.dependencies.permissions import require_admin
from app.dependencies.discussion import check_category_access



from sqlalchemy import func
from sqlalchemy.orm import joinedload

from app.models.discussion import (
    DiscussionCategory,
    DiscussionTopic,
    DiscussionComment,
    DiscussionLike,
    DiscussionReport,
    DiscussionNotification,
)

from app.schemas.discussion import (
    DiscussionTopicCreate,
    DiscussionTopicUpdate,
    DiscussionTopicResponse,
    DiscussionTopicListResponse,
    DiscussionNotificationResponse,
    DiscussionNotificationReadResponse,
)

from app.dependencies.auth import get_current_user
from app.dependencies.discussion import check_category_access

from sqlalchemy import select, func
from sqlalchemy.orm import joinedload

from app.models.discussion import (
    DiscussionTopic,
    DiscussionComment,
)

from app.schemas.discussion import (
    DiscussionCommentCreate,
    DiscussionReplyCreate,
    DiscussionCommentUpdate,
    DiscussionCommentResponse,
    DiscussionCommentTreeResponse,
)


from app.models.discussion import DiscussionLike
from app.schemas.discussion import (
    DiscussionLikeResponse,
    DiscussionLikeCountResponse,
)


from app.models.discussion import DiscussionReport
from app.schemas.discussion import (
    DiscussionReportCreate,
    DiscussionReportUpdate,
    DiscussionReportResponse,
)


from sqlalchemy import select, update, desc

from app.models.discussion import DiscussionNotification

from app.schemas.discussion import (
    DiscussionNotificationResponse,
    DiscussionNotificationReadResponse,
)

router = APIRouter(prefix="/discussions", tags=["Discussions"])


def create_category_slug(name: str) -> str:
    """Convert a category name into a URL-friendly slug."""
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "discussion"


def get_unique_category_slug(
    db: Session,
    name: str,
    exclude_id: int | None = None,
) -> str:
    base_slug = create_category_slug(name)
    slug = base_slug
    counter = 1

    while True:
        query = select(DiscussionCategory).where(
            DiscussionCategory.slug == slug
        )

        if exclude_id is not None:
            query = query.where(
                DiscussionCategory.id != exclude_id
            )

        existing = db.scalar(query)

        if not existing:
            return slug

        counter += 1
        slug = f"{base_slug}-{counter}"


def create_discussion_notification(
    db: Session,
    recipient_user_id: int,
    actor_user_id: int | None,
    notification_type: str,
    message: str,
    topic_id: int | None = None,
    comment_id: int | None = None,
):
    """
    Create a notification for a user.

    A user will not receive a notification for their own action.
    """

    if recipient_user_id == actor_user_id:
        return None

    notification = DiscussionNotification(
        user_id=recipient_user_id,
        actor_user_id=actor_user_id,
        topic_id=topic_id,
        comment_id=comment_id,
        notification_type=notification_type,
        message=message,
        is_read=False,
    )

    db.add(notification)
    db.flush()

    return notification


# =========================================================
# CATEGORY ENDPOINTS
# =========================================================

@router.get(
    "/categories",
    response_model=list[DiscussionCategoryResponse],
)
def list_discussion_categories(
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    """
    List active discussion categories.

    Visitors see public categories.
    Active members can also see members-only categories.
    Administrators can see all categories, including inactive ones.
    """

    query = select(DiscussionCategory).order_by(
        DiscussionCategory.display_order.asc(),
        DiscussionCategory.name.asc(),
    )

    if current_user and current_user.is_admin:
        categories = db.scalars(query).all()
        return categories

    query = query.where(
        DiscussionCategory.is_active.is_(True)
    )

    categories = db.scalars(query).all()

    visible_categories = []

    for category in categories:
        if category.access_level == "public":
            visible_categories.append(category)
            continue

        if current_user:
            try:
                check_category_access(
                    category,
                    current_user,
                    db,
                )
                visible_categories.append(category)
            except HTTPException:
                continue

    return visible_categories


@router.post(
    "/admin/categories",
    response_model=DiscussionCategoryResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_discussion_category(
    payload: DiscussionCategoryCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Create a discussion category."""

    name = payload.name.strip()

    if not name:
        raise HTTPException(
            status_code=400,
            detail="Category name cannot be empty.",
        )

    existing = db.scalar(
        select(DiscussionCategory).where(
            DiscussionCategory.name == name
        )
    )

    if existing:
        raise HTTPException(
            status_code=400,
            detail="A category with this name already exists.",
        )

    category = DiscussionCategory(
        name=name,
        slug=get_unique_category_slug(db, name),
        description=payload.description,
        access_level=payload.access_level,
        is_active=True,
        display_order=payload.display_order,
    )

    db.add(category)
    db.commit()
    db.refresh(category)

    return category


@router.put(
    "/admin/categories/{category_id}",
    response_model=DiscussionCategoryResponse,
)
def update_discussion_category(
    category_id: int,
    payload: DiscussionCategoryUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Update a discussion category."""

    category = db.get(DiscussionCategory, category_id)

    if not category:
        raise HTTPException(
            status_code=404,
            detail="Discussion category not found.",
        )

    updates = payload.model_dump(exclude_unset=True)

    if not updates:
        raise HTTPException(
            status_code=400,
            detail="No changes were supplied.",
        )

    if "name" in updates:
        name = updates["name"].strip()

        if not name:
            raise HTTPException(
                status_code=400,
                detail="Category name cannot be empty.",
            )

        existing = db.scalar(
            select(DiscussionCategory).where(
                DiscussionCategory.name == name,
                DiscussionCategory.id != category_id,
            )
        )

        if existing:
            raise HTTPException(
                status_code=400,
                detail="Another category already uses this name.",
            )

        category.name = name
        category.slug = get_unique_category_slug(
            db,
            name,
            exclude_id=category_id,
        )

    for field in (
        "description",
        "access_level",
        "is_active",
        "display_order",
    ):
        if field in updates:
            setattr(category, field, updates[field])

    db.commit()
    db.refresh(category)

    return category


@router.delete(
    "/admin/categories/{category_id}",
)
def delete_discussion_category(
    category_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """
    Delete a category only when it has no topics.

    Categories containing discussions should normally be deactivated
    instead, so existing discussions and their history are preserved.
    """

    category = db.get(DiscussionCategory, category_id)

    if not category:
        raise HTTPException(
            status_code=404,
            detail="Discussion category not found.",
        )

    if category.topics:
        raise HTTPException(
            status_code=400,
            detail=(
                "This category contains discussions. "
                "Deactivate it instead of deleting it."
            ),
        )

    db.delete(category)
    db.commit()

    return {
        "message": "Discussion category deleted successfully."
    }





# =========================================================
# TOPIC ENDPOINTS
# =========================================================

@router.post(
    "/topics",
    response_model=DiscussionTopicResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_discussion_topic(
    payload: DiscussionTopicCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    category = db.get(
        DiscussionCategory,
        payload.category_id,
    )

    if not category:
        raise HTTPException(
            status_code=404,
            detail="Discussion category not found.",
        )

    check_category_access(category, current_user, db)

    if not category.is_active:
        raise HTTPException(
            status_code=400,
            detail="This discussion category is inactive.",
        )

    title = payload.title.strip()
    content = payload.content.strip()

    if not title or not content:
        raise HTTPException(
            status_code=400,
            detail="Topic title and content cannot be empty.",
        )

    topic = DiscussionTopic(
        category_id=category.id,
        user_id=current_user.id,
        title=title,
        content=content,
    )

    db.add(topic)
    db.commit()
    db.refresh(topic)

    return db.scalar(
        select(DiscussionTopic)
        .options(
            joinedload(DiscussionTopic.user),
            joinedload(DiscussionTopic.category),
        )
        .where(DiscussionTopic.id == topic.id)
    )


@router.get(
    "/categories/{category_id}/topics",
    response_model=list[DiscussionTopicListResponse],
)
def list_category_topics(
    category_id: int,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    category = db.get(
        DiscussionCategory,
        category_id,
    )

    if not category:
        raise HTTPException(
            status_code=404,
            detail="Discussion category not found.",
        )

    check_category_access(category, current_user, db)

    query = (
        select(DiscussionTopic)
        .options(
            joinedload(DiscussionTopic.user),
            joinedload(DiscussionTopic.category),
        )
        .where(
            DiscussionTopic.category_id == category_id,
            DiscussionTopic.is_hidden.is_(False),
        )
        .order_by(
            DiscussionTopic.is_pinned.desc(),
            DiscussionTopic.updated_at.desc(),
        )
    )

    topics = db.scalars(query).unique().all()

    results = []

    for topic in topics:
        comment_count = db.scalar(
            select(func.count(DiscussionComment.id)).where(
                DiscussionComment.topic_id == topic.id,
                DiscussionComment.is_hidden.is_(False),
            )
        ) or 0

        like_count = db.scalar(
            select(func.count(DiscussionLike.id)).where(
                DiscussionLike.topic_id == topic.id
            )
        ) or 0

        results.append({
            "id": topic.id,
            "category_id": topic.category_id,
            "user_id": topic.user_id,
            "title": topic.title,
            "content": topic.content,
            "is_pinned": topic.is_pinned,
            "is_locked": topic.is_locked,
            "view_count": topic.view_count,
            "created_at": topic.created_at,
            "updated_at": topic.updated_at,
            "username": topic.user.username,
            "category_name": topic.category.name,
            "comment_count": comment_count,
            "like_count": like_count,
        })

    return results


@router.get(
    "/topics/{topic_id}",
    response_model=DiscussionTopicResponse,
)
def get_discussion_topic(
    topic_id: int,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    topic = db.scalar(
        select(DiscussionTopic)
        .options(
            joinedload(DiscussionTopic.user),
            joinedload(DiscussionTopic.category),
        )
        .where(
            DiscussionTopic.id == topic_id
        )
    )

    if not topic or topic.is_hidden:
        raise HTTPException(
            status_code=404,
            detail="Discussion topic not found.",
        )

    check_category_access(
        topic.category,
        current_user,
        db,
    )

    topic.view_count += 1

    db.commit()
    db.refresh(topic)

    return topic


@router.put(
    "/topics/{topic_id}",
    response_model=DiscussionTopicResponse,
)
def update_discussion_topic(
    topic_id: int,
    payload: DiscussionTopicUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    topic = db.get(
        DiscussionTopic,
        topic_id,
    )

    if not topic or topic.is_hidden:
        raise HTTPException(
            status_code=404,
            detail="Discussion topic not found.",
        )

    check_category_access(
        topic.category,
        current_user,
        db,
    )

    if topic.user_id != current_user.id and not current_user.is_admin:
        raise HTTPException(
            status_code=403,
            detail="You can only edit your own topics.",
        )

    updates = payload.model_dump(exclude_unset=True)

    if not updates:
        raise HTTPException(
            status_code=400,
            detail="No changes were supplied.",
        )

    if "category_id" in updates:
        category = db.get(
            DiscussionCategory,
            updates["category_id"],
        )

        if not category:
            raise HTTPException(
                status_code=404,
                detail="Discussion category not found.",
            )

        check_category_access(category, current_user, db)

        if not category.is_active:
            raise HTTPException(
                status_code=400,
                detail="This category is inactive.",
            )

        topic.category_id = category.id

    if "title" in updates:
        title = updates["title"].strip()

        if not title:
            raise HTTPException(
                status_code=400,
                detail="Topic title cannot be empty.",
            )

        topic.title = title

    if "content" in updates:
        content = updates["content"].strip()

        if not content:
            raise HTTPException(
                status_code=400,
                detail="Topic content cannot be empty.",
            )

        topic.content = content

    db.commit()
    db.refresh(topic)

    return db.scalar(
        select(DiscussionTopic)
        .options(
            joinedload(DiscussionTopic.user),
            joinedload(DiscussionTopic.category),
        )
        .where(DiscussionTopic.id == topic.id)
    )


@router.delete(
    "/topics/{topic_id}",
)
def delete_discussion_topic(
    topic_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    topic = db.get(
        DiscussionTopic,
        topic_id,
    )

    if not topic:
        raise HTTPException(
            status_code=404,
            detail="Discussion topic not found.",
        )

    check_category_access(
        topic.category,
        current_user,
        db,
    )

    if topic.user_id != current_user.id and not current_user.is_admin:
        raise HTTPException(
            status_code=403,
            detail="You can only delete your own topics.",
        )

    # Preserve discussion history by hiding rather than physically deleting.
    topic.is_hidden = True

    db.commit()

    return {
        "message": "Discussion topic deleted successfully."
    }


# =========================================================
# ADMIN TOPIC MODERATION
# =========================================================

@router.patch(
    "/admin/topics/{topic_id}/pin",
)
def pin_discussion_topic(
    topic_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    topic = db.get(DiscussionTopic, topic_id)

    if not topic:
        raise HTTPException(
            status_code=404,
            detail="Discussion topic not found.",
        )

    topic.is_pinned = not topic.is_pinned

    db.commit()

    return {
        "message": "Topic pin status updated.",
        "is_pinned": topic.is_pinned,
    }


@router.patch(
    "/admin/topics/{topic_id}/lock",
)
def lock_discussion_topic(
    topic_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    topic = db.get(DiscussionTopic, topic_id)

    if not topic:
        raise HTTPException(
            status_code=404,
            detail="Discussion topic not found.",
        )

    topic.is_locked = not topic.is_locked

    db.commit()

    return {
        "message": "Topic lock status updated.",
        "is_locked": topic.is_locked,
    }


@router.patch(
    "/admin/topics/{topic_id}/hide",
)
def hide_discussion_topic(
    topic_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    topic = db.get(DiscussionTopic, topic_id)

    if not topic:
        raise HTTPException(
            status_code=404,
            detail="Discussion topic not found.",
        )

    topic.is_hidden = not topic.is_hidden

    db.commit()

    return {
        "message": "Topic visibility updated.",
        "is_hidden": topic.is_hidden,
    }





# =========================================================
# COMMENT AND REPLY ENDPOINTS
# =========================================================

def get_accessible_topic(
    topic_id: int,
    db: Session,
    current_user: User | None,
):
    topic = db.scalar(
        select(DiscussionTopic)
        .options(joinedload(DiscussionTopic.category))
        .where(DiscussionTopic.id == topic_id)
    )

    if not topic or topic.is_hidden:
        raise HTTPException(
            status_code=404,
            detail="Discussion topic not found.",
        )

    check_category_access(
        topic.category,
        current_user,
        db,
    )

    return topic


@router.post(
    "/topics/{topic_id}/comments",
    response_model=DiscussionCommentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_discussion_comment(
    topic_id: int,
    payload: DiscussionCommentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    topic = get_accessible_topic(
        topic_id,
        db,
        current_user,
    )

    if topic.is_locked and not current_user.is_admin:
        raise HTTPException(
            status_code=403,
            detail="This discussion is locked.",
        )

    content = payload.content.strip()

    if not content:
        raise HTTPException(
            status_code=400,
            detail="Comment cannot be empty.",
        )

    comment = DiscussionComment(
        topic_id=topic.id,
        user_id=current_user.id,
        parent_id=None,
        content=content,
    )

    db.add(comment)
    db.flush()

    create_discussion_notification(
        db=db,
        recipient_user_id=topic.user_id,
        actor_user_id=current_user.id,
        notification_type="new_comment",
        message=f"{current_user.username} commented on your discussion: {topic.title}",
        topic_id=topic.id,
        comment_id=comment.id,
    )

    db.commit()
    db.refresh(comment)

    return db.scalar(
        select(DiscussionComment)
        .options(joinedload(DiscussionComment.user))
        .where(DiscussionComment.id == comment.id)
    )


@router.post(
    "/topics/{topic_id}/comments/{comment_id}/replies",
    response_model=DiscussionCommentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_discussion_reply(
    topic_id: int,
    comment_id: int,
    payload: DiscussionReplyCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    topic = get_accessible_topic(
        topic_id,
        db,
        current_user,
    )

    if topic.is_locked and not current_user.is_admin:
        raise HTTPException(
            status_code=403,
            detail="This discussion is locked.",
        )

    parent = db.get(
        DiscussionComment,
        comment_id,
    )

    if (
        not parent
        or parent.topic_id != topic_id
        or parent.is_hidden
    ):
        raise HTTPException(
            status_code=404,
            detail="Comment not found.",
        )

    content = payload.content.strip()

    if not content:
        raise HTTPException(
            status_code=400,
            detail="Reply cannot be empty.",
        )

    reply = DiscussionComment(
        topic_id=topic.id,
        user_id=current_user.id,
        parent_id=parent.id,
        content=content,
    )

    db.add(reply)
    db.flush()

    create_discussion_notification(
        db=db,
        recipient_user_id=parent.user_id,
        actor_user_id=current_user.id,
        notification_type="new_reply",
        message=f"{current_user.username} replied to your comment.",
        topic_id=topic.id,
        comment_id=reply.id,
    )

    db.commit()
    db.refresh(reply)




    return db.scalar(
        select(DiscussionComment)
        .options(joinedload(DiscussionComment.user))
        .where(DiscussionComment.id == reply.id)
    )


@router.get(
    "/topics/{topic_id}/comments",
    response_model=list[DiscussionCommentTreeResponse],
)
def list_discussion_comments(
    topic_id: int,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    topic = get_accessible_topic(
        topic_id,
        db,
        current_user,
    )

    comments = db.scalars(
        select(DiscussionComment)
        .options(joinedload(DiscussionComment.user))
        .where(
            DiscussionComment.topic_id == topic.id,
            DiscussionComment.is_hidden.is_(False),
        )
        .order_by(DiscussionComment.created_at.asc())
    ).unique().all()

    like_counts = dict(
        db.execute(
            select(
                DiscussionLike.comment_id,
                func.count(DiscussionLike.id),
            )
            .where(
                DiscussionLike.comment_id.is_not(None)
            )
            .group_by(DiscussionLike.comment_id)
        ).all()
    )

    comment_map = {}

    for comment in comments:
        comment_map[comment.id] = {
            "id": comment.id,
            "topic_id": comment.topic_id,
            "user_id": comment.user_id,
            "parent_id": comment.parent_id,
            "content": comment.content,
            "is_hidden": False,
            "created_at": comment.created_at,
            "updated_at": comment.updated_at,
            "user": comment.user,
            "like_count": like_counts.get(comment.id, 0),
            "replies": [],
        }

    roots = []

    for comment in comments:
        item = comment_map[comment.id]

        if comment.parent_id is None:
            roots.append(item)
        elif comment.parent_id in comment_map:
            comment_map[comment.parent_id]["replies"].append(item)

    return roots


@router.put(
    "/comments/{comment_id}",
    response_model=DiscussionCommentResponse,
)
def update_discussion_comment(
    comment_id: int,
    payload: DiscussionCommentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    comment = db.get(
        DiscussionComment,
        comment_id,
    )

    if not comment or comment.is_hidden:
        raise HTTPException(
            status_code=404,
            detail="Comment not found.",
        )

    topic = get_accessible_topic(
        comment.topic_id,
        db,
        current_user,
    )

    if comment.user_id != current_user.id and not current_user.is_admin:
        raise HTTPException(
            status_code=403,
            detail="You can only edit your own comments.",
        )

    content = payload.content.strip()

    if not content:
        raise HTTPException(
            status_code=400,
            detail="Comment cannot be empty.",
        )

    comment.content = content

    db.commit()
    db.refresh(comment)

    return db.scalar(
        select(DiscussionComment)
        .options(joinedload(DiscussionComment.user))
        .where(DiscussionComment.id == comment.id)
    )


@router.delete(
    "/comments/{comment_id}",
)
def delete_discussion_comment(
    comment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    comment = db.get(
        DiscussionComment,
        comment_id,
    )

    if not comment:
        raise HTTPException(
            status_code=404,
            detail="Comment not found.",
        )

    get_accessible_topic(
        comment.topic_id,
        db,
        current_user,
    )

    if comment.user_id != current_user.id and not current_user.is_admin:
        raise HTTPException(
            status_code=403,
            detail="You can only delete your own comments.",
        )

    # Preserve replies and discussion history.
    comment.is_hidden = True

    db.commit()

    return {
        "message": "Comment deleted successfully."
    }


# =========================================================
# ADMIN COMMENT MODERATION
# =========================================================

@router.patch(
    "/admin/comments/{comment_id}/hide",
)
def hide_discussion_comment(
    comment_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    comment = db.get(
        DiscussionComment,
        comment_id,
    )

    if not comment:
        raise HTTPException(
            status_code=404,
            detail="Comment not found.",
        )

    comment.is_hidden = not comment.is_hidden

    db.commit()

    return {
        "message": "Comment visibility updated.",
        "is_hidden": comment.is_hidden,
    }



# =========================================================
# DISCUSSION LIKE ENDPOINTS
# =========================================================

def add_discussion_like(
    db: Session,
    current_user: User,
    topic_id: int | None = None,
    comment_id: int | None = None,
):
    if (topic_id is None) == (comment_id is None):
        raise HTTPException(
            status_code=400,
            detail="Provide exactly one topic or comment.",
        )

    if topic_id is not None:
        existing = db.scalar(
            select(DiscussionLike).where(
                DiscussionLike.user_id == current_user.id,
                DiscussionLike.topic_id == topic_id,
            )
        )
    else:
        existing = db.scalar(
            select(DiscussionLike).where(
                DiscussionLike.user_id == current_user.id,
                DiscussionLike.comment_id == comment_id,
            )
        )

    if existing:
        return existing, False

    like = DiscussionLike(
        user_id=current_user.id,
        topic_id=topic_id,
        comment_id=comment_id,
    )

    db.add(like)

    try:
        # Save the new row within the current transaction.
        # Do not commit here; the endpoint handles the commit.
        db.flush()

    except IntegrityError:
        db.rollback()

        raise HTTPException(
            status_code=409,
            detail="You have already liked this item.",
        )

    return like, True




def remove_discussion_like(
    db: Session,
    current_user: User,
    topic_id: int | None = None,
    comment_id: int | None = None,
):
    query = select(DiscussionLike).where(
        DiscussionLike.user_id == current_user.id
    )

    if topic_id is not None:
        query = query.where(
            DiscussionLike.topic_id == topic_id
        )
    else:
        query = query.where(
            DiscussionLike.comment_id == comment_id
        )

    like = db.scalar(query)

    if not like:
        raise HTTPException(
            status_code=404,
            detail="You have not liked this item.",
        )

    db.delete(like)
    db.commit()

    return {
        "message": "Like removed successfully."
    }


@router.post(
    "/topics/{topic_id}/like",
    response_model=DiscussionLikeResponse,
)
def like_discussion_topic(
    topic_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    topic = get_accessible_topic(
        topic_id,
        db,
        current_user,
    )

    like, created = add_discussion_like(
        db,
        current_user,
        topic_id=topic.id,
    )

    if created:
        create_discussion_notification(
            db=db,
            recipient_user_id=topic.user_id,
            actor_user_id=current_user.id,
            notification_type="topic_like",
            message=(
                f"{current_user.username} liked your discussion: "
                f"{topic.title}"
            ),
            topic_id=topic.id,
        )

        db.commit()
        db.refresh(like)

    return like




@router.delete(
    "/topics/{topic_id}/like",
)
def unlike_discussion_topic(
    topic_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    get_accessible_topic(
        topic_id,
        db,
        current_user,
    )

    return remove_discussion_like(
        db,
        current_user,
        topic_id=topic_id,
    )


@router.post(
    "/comments/{comment_id}/like",
    response_model=DiscussionLikeResponse,
)
def like_discussion_comment(
    comment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    comment = db.get(
        DiscussionComment,
        comment_id,
    )

    if not comment or comment.is_hidden:
        raise HTTPException(
            status_code=404,
            detail="Comment not found.",
        )

    get_accessible_topic(
        comment.topic_id,
        db,
        current_user,
    )

    like, created = add_discussion_like(
        db,
        current_user,
        comment_id=comment.id,
    )

    if created:
        create_discussion_notification(
            db=db,
            recipient_user_id=comment.user_id,
            actor_user_id=current_user.id,
            notification_type="comment_like",
            message=(
                f"{current_user.username} liked your comment."
            ),
            topic_id=comment.topic_id,
            comment_id=comment.id,
        )

        db.commit()
        db.refresh(like)

    return like




@router.delete(
    "/comments/{comment_id}/like",
)
def unlike_discussion_comment(
    comment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    comment = db.get(
        DiscussionComment,
        comment_id,
    )

    if not comment or comment.is_hidden:
        raise HTTPException(
            status_code=404,
            detail="Comment not found.",
        )

    get_accessible_topic(
        comment.topic_id,
        db,
        current_user,
    )

    return remove_discussion_like(
        db,
        current_user,
        comment_id=comment_id,
    )


# =========================================================
# LIKE COUNT AND USER LIKE STATUS
# =========================================================

@router.get(
    "/topics/{topic_id}/likes",
    response_model=DiscussionLikeCountResponse,
)
def get_topic_like_count(
    topic_id: int,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    topic = get_accessible_topic(
        topic_id,
        db,
        current_user,
    )

    like_count = db.scalar(
        select(func.count(DiscussionLike.id)).where(
            DiscussionLike.topic_id == topic.id
        )
    ) or 0

    liked = False

    if current_user:
        liked = db.scalar(
            select(DiscussionLike.id).where(
                DiscussionLike.topic_id == topic.id,
                DiscussionLike.user_id == current_user.id,
            )
        ) is not None

    return {
        "topic_id": topic.id,
        "comment_id": None,
        "like_count": like_count,
        "liked_by_current_user": liked,
    }


@router.get(
    "/comments/{comment_id}/likes",
    response_model=DiscussionLikeCountResponse,
)
def get_comment_like_count(
    comment_id: int,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    comment = db.get(
        DiscussionComment,
        comment_id,
    )

    if not comment or comment.is_hidden:
        raise HTTPException(
            status_code=404,
            detail="Comment not found.",
        )

    get_accessible_topic(
        comment.topic_id,
        db,
        current_user,
    )

    like_count = db.scalar(
        select(func.count(DiscussionLike.id)).where(
            DiscussionLike.comment_id == comment.id
        )
    ) or 0

    liked = False

    if current_user:
        liked = db.scalar(
            select(DiscussionLike.id).where(
                DiscussionLike.comment_id == comment.id,
                DiscussionLike.user_id == current_user.id,
            )
        ) is not None

    return {
        "topic_id": None,
        "comment_id": comment.id,
        "like_count": like_count,
        "liked_by_current_user": liked,
    }



# =========================================================
# DISCUSSION REPORT ENDPOINTS
# =========================================================

@router.post(
    "/reports",
    response_model=DiscussionReportResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_discussion_report(
    payload: DiscussionReportCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if payload.topic_id is not None:
        topic = get_accessible_topic(
            payload.topic_id,
            db,
            current_user,
        )

        if topic.user_id == current_user.id:
            raise HTTPException(
                status_code=400,
                detail="You cannot report your own topic.",
            )

    else:
        comment = db.get(
            DiscussionComment,
            payload.comment_id,
        )

        if not comment or comment.is_hidden:
            raise HTTPException(
                status_code=404,
                detail="Comment not found.",
            )

        get_accessible_topic(
            comment.topic_id,
            db,
            current_user,
        )

        if comment.user_id == current_user.id:
            raise HTTPException(
                status_code=400,
                detail="You cannot report your own comment.",
            )

    report = DiscussionReport(
        user_id=current_user.id,
        topic_id=payload.topic_id,
        comment_id=payload.comment_id,
        reason=payload.reason.strip(),
        description=payload.description,
        status="pending",
    )

    db.add(report)
    db.commit()
    db.refresh(report)

    return report


# =========================================================
# ADMIN REPORT MANAGEMENT
# =========================================================

@router.get(
    "/admin/reports",
    response_model=list[DiscussionReportResponse],
)
def list_discussion_reports(
    report_status: str | None = None,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    query = select(DiscussionReport).order_by(
        DiscussionReport.created_at.desc()
    )

    if report_status:
        if report_status not in (
            "pending",
            "reviewed",
            "dismissed",
            "actioned",
        ):
            raise HTTPException(
                status_code=400,
                detail="Invalid report status.",
            )

        query = query.where(
            DiscussionReport.status == report_status
        )

    return db.scalars(query).all()



@router.patch(
    "/admin/reports/{report_id}",
    response_model=DiscussionReportResponse,
)
def update_discussion_report(
    report_id: int,
    payload: DiscussionReportUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    report = db.get(
        DiscussionReport,
        report_id,
    )

    if not report:
        raise HTTPException(
            status_code=404,
            detail="Discussion report not found.",
        )

    allowed_statuses = (
        "pending",
        "reviewed",
        "dismissed",
        "actioned",
    )

    if payload.status not in allowed_statuses:
        raise HTTPException(
            status_code=400,
            detail="Invalid report status.",
        )

    old_status = report.status
    new_status = payload.status

    report.status = new_status
    report.reviewed_by = admin.id
    report.reviewed_at = datetime.now(timezone.utc)

    # Notify the reporter only when the status actually changes.
    if old_status != new_status:
        create_discussion_notification(
            db=db,
            recipient_user_id=report.user_id,
            actor_user_id=admin.id,
            notification_type="report_reviewed",
            message=(
                f"Your discussion report #{report.id} "
                f"has been {new_status}."
            ),
            topic_id=report.topic_id,
            comment_id=report.comment_id,
        )

    db.commit()
    db.refresh(report)

    return report



@router.get(
    "/notifications",
    response_model=list[DiscussionNotificationResponse],
)
def get_my_notifications(
    unread_only: bool = False,
    limit: int = 50,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if limit < 1 or limit > 100:
        raise HTTPException(
            status_code=400,
            detail="Limit must be between 1 and 100.",
        )

    if offset < 0:
        raise HTTPException(
            status_code=400,
            detail="Offset cannot be negative.",
        )

    query = select(DiscussionNotification).where(
        DiscussionNotification.user_id == current_user.id
    )

    if unread_only:
        query = query.where(
            DiscussionNotification.is_read.is_(False)
        )

    query = query.order_by(
        desc(DiscussionNotification.created_at)
    ).limit(limit).offset(offset)

    return db.scalars(query).all()


@router.patch(
    "/notifications/{notification_id}/read",
    response_model=DiscussionNotificationReadResponse,
)
def mark_notification_as_read(
    notification_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    notification = db.scalar(
        select(DiscussionNotification).where(
            DiscussionNotification.id == notification_id,
            DiscussionNotification.user_id == current_user.id,
        )
    )

    if notification is None:
        raise HTTPException(
            status_code=404,
            detail="Notification not found.",
        )

    notification.is_read = True

    db.commit()
    db.refresh(notification)

    return {
        "message": "Notification marked as read.",
        "notification_id": notification.id,
        "is_read": notification.is_read,
    }


@router.patch("/notifications/read-all")
def mark_all_notifications_as_read(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    result = db.execute(
        update(DiscussionNotification)
        .where(
            DiscussionNotification.user_id == current_user.id,
            DiscussionNotification.is_read.is_(False),
        )
        .values(is_read=True)
    )

    db.commit()

    return {
        "message": "All notifications marked as read.",
        "updated_count": result.rowcount,
    }



@router.get("/notifications/unread-count")
def get_unread_notification_count(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    count = db.scalar(
        select(func.count(DiscussionNotification.id)).where(
            DiscussionNotification.user_id == current_user.id,
            DiscussionNotification.is_read.is_(False),
        )
    )

    return {
        "unread_count": count or 0
    }




