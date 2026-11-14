
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


# =========================================================
# SHARED USER INFORMATION
# =========================================================

class DiscussionUserResponse(BaseModel):
    id: int
    username: str

    model_config = ConfigDict(from_attributes=True)



# =========================================================
# DISCUSSION CATEGORY SCHEMAS
# =========================================================

class DiscussionCategoryBase(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    description: str | None = None

    access_level: str = Field(
        default="public",
        pattern="^(public|members)$",
    )

    display_order: int = 0


class DiscussionCategoryCreate(DiscussionCategoryBase):
    pass


class DiscussionCategoryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=100)
    description: str | None = None

    access_level: str | None = Field(
        default=None,
        pattern="^(public|members)$",
    )

    is_active: bool | None = None
    display_order: int | None = None


class DiscussionCategoryResponse(DiscussionCategoryBase):
    id: int
    slug: str
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)



# =========================================================
# DISCUSSION TOPIC SCHEMAS
# =========================================================

class DiscussionTopicCreate(BaseModel):
    category_id: int
    title: str = Field(min_length=5, max_length=250)
    content: str = Field(min_length=1)


class DiscussionTopicUpdate(BaseModel):
    category_id: int | None = None
    title: str | None = Field(default=None, min_length=5, max_length=250)
    content: str | None = Field(default=None, min_length=1)


class DiscussionTopicResponse(BaseModel):
    id: int
    category_id: int
    user_id: int

    title: str
    content: str

    is_pinned: bool
    is_locked: bool
    is_hidden: bool

    view_count: int

    created_at: datetime
    updated_at: datetime

    user: DiscussionUserResponse
    category: DiscussionCategoryResponse

    model_config = ConfigDict(from_attributes=True)


class DiscussionTopicListResponse(BaseModel):
    id: int
    category_id: int
    user_id: int

    title: str
    content: str

    is_pinned: bool
    is_locked: bool
    view_count: int

    created_at: datetime
    updated_at: datetime

    username: str
    category_name: str

    comment_count: int = 0
    like_count: int = 0

    model_config = ConfigDict(from_attributes=True)


# =========================================================
# DISCUSSION COMMENT AND REPLY SCHEMAS
# =========================================================

class DiscussionCommentCreate(BaseModel):
    content: str = Field(min_length=1)


class DiscussionReplyCreate(BaseModel):
    content: str = Field(min_length=1)


class DiscussionCommentUpdate(BaseModel):
    content: str = Field(min_length=1)


class DiscussionCommentResponse(BaseModel):
    id: int
    topic_id: int
    user_id: int
    parent_id: int | None

    content: str
    is_hidden: bool

    created_at: datetime
    updated_at: datetime

    user: DiscussionUserResponse

    model_config = ConfigDict(from_attributes=True)


class DiscussionCommentTreeResponse(BaseModel):
    id: int
    topic_id: int
    user_id: int
    parent_id: int | None

    content: str
    is_hidden: bool

    created_at: datetime
    updated_at: datetime

    user: DiscussionUserResponse

    like_count: int = 0
    replies: list["DiscussionCommentTreeResponse"] = Field(
        default_factory=list
    )

    model_config = ConfigDict(from_attributes=True)


# =========================================================
# DISCUSSION LIKE SCHEMAS
# =========================================================

class DiscussionLikeResponse(BaseModel):
    id: int
    user_id: int
    topic_id: int | None
    comment_id: int | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DiscussionLikeCountResponse(BaseModel):
    topic_id: int | None = None
    comment_id: int | None = None

    like_count: int
    liked_by_current_user: bool = False


# =========================================================
# DISCUSSION REPORT SCHEMAS
# =========================================================

class DiscussionReportCreate(BaseModel):
    topic_id: int | None = Field(default=None, examples=[1])
    comment_id: int | None = Field(default=None, examples=[1])
    reason: str = Field(min_length=3, max_length=100)
    description: str | None = None

    @model_validator(mode="after")
    def validate_target(self):
        if (self.topic_id is None) == (self.comment_id is None):
            raise ValueError(
                "Provide either topic_id or comment_id, not both."
            )
        return self

    

class DiscussionReportUpdate(BaseModel):
    status: str = Field(
        pattern="^(reviewed|dismissed|actioned)$"
    )


class DiscussionReportResponse(BaseModel):
    id: int
    user_id: int

    topic_id: int | None
    comment_id: int | None

    reason: str
    description: str | None

    status: str

    reviewed_by: int | None
    created_at: datetime
    reviewed_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


# =========================================================
# DISCUSSION NOTIFICATION SCHEMAS
# =========================================================

class DiscussionNotificationResponse(BaseModel):
    id: int
    user_id: int
    actor_user_id: int | None

    topic_id: int | None
    comment_id: int | None

    notification_type: str
    message: str

    is_read: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DiscussionNotificationReadResponse(BaseModel):
    message: str
    notification_id: int
    is_read: bool
