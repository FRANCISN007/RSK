
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


# ============================================================
# PAPER CATEGORY
# ============================================================

class PaperCategoryCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    slug: str = Field(..., min_length=1, max_length=120)
    description: str | None = None
    is_active: bool = True
    display_order: int = 0


class PaperCategoryUpdate(BaseModel):
    name: str | None = Field(
        None,
        min_length=1,
        max_length=100,
    )
    slug: str | None = Field(
        None,
        min_length=1,
        max_length=120,
    )
    description: str | None = None
    is_active: bool | None = None
    display_order: int | None = None


class PaperCategoryResponse(BaseModel):
    id: int
    name: str
    slug: str
    description: str | None
    is_active: bool
    display_order: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ============================================================
# PAPER
# ============================================================

class PaperCreate(BaseModel):
    category_id: int
    name: str = Field(
        ...,
        min_length=1,
        max_length=150,
    )
    slug: str = Field(
        ...,
        min_length=1,
        max_length=180,
    )
    description: str | None = None
    is_active: bool = True
    display_order: int = 0


class PaperUpdate(BaseModel):
    category_id: int | None = None
    name: str | None = Field(
        None,
        min_length=1,
        max_length=150,
    )
    slug: str | None = Field(
        None,
        min_length=1,
        max_length=180,
    )
    description: str | None = None
    is_active: bool | None = None
    display_order: int | None = None


class PaperResponse(BaseModel):
    id: int
    category_id: int
    name: str
    slug: str
    description: str | None
    is_active: bool
    display_order: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ============================================================
# PAPER PAGE CREATE
# ============================================================

class PaperPageCreate(BaseModel):
    page_number: int = Field(
        ...,
        ge=1,
        le=4,
    )


# ============================================================
# PAPER WEEK
# ============================================================

class PaperWeekCreate(BaseModel):
    year: int = Field(
        ...,
        ge=2000,
        le=2100,
    )
    week_number: int = Field(
        ...,
        ge=1,
        le=53,
    )


class PaperWeekUpdate(BaseModel):
    status: str | None = None


class PaperWeekResponse(BaseModel):
    id: int
    category_id: int
    year: int
    week_number: int
    status: str
    published_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ============================================================
# PAPER PAGE
# ============================================================

class PaperPageResponse(BaseModel):
    id: int
    paper_id: int
    page_number: int
    file_path: str | None = None
    file_type: str | None = None
    is_marked: bool
    uploaded_at: datetime
    marked_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)

# ============================================================
# PUBLIC PAPER DISPLAY
# ============================================================

class PublicPaperPageResponse(BaseModel):
    id: int
    page_number: int
    file_path: str
    file_type: str
    is_marked: bool

    model_config = ConfigDict(from_attributes=True)


class PublicPaperResponse(BaseModel):
    id: int
    category_id: int
    name: str
    slug: str
    description: str | None

    week_id: int
    year: int
    week_number: int
    status: str

    pages: list[PublicPaperPageResponse]

    model_config = ConfigDict(from_attributes=True)

