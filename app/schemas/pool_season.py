from datetime import datetime, time

from pydantic import BaseModel, ConfigDict, Field


class PoolSeasonCreate(BaseModel):
    name: str = Field(
        min_length=1,
        max_length=100,
    )

    slug: str = Field(
        min_length=1,
        max_length=100,
    )

    closing_weekday: int = Field(
        ge=1,
        le=7,
    )

    closing_time: time

    is_active: bool = True


class PoolSeasonUpdate(BaseModel):
    name: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
    )

    slug: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
    )

    closing_weekday: int | None = Field(
        default=None,
        ge=1,
        le=7,
    )

    closing_time: time | None = None

    is_active: bool | None = None


class PoolSeasonResponse(BaseModel):
    id: int
    name: str
    slug: str
    closing_weekday: int
    closing_time: time
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
    )