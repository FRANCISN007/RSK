from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class FreeGameCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    season_id: int
    pool_week_id: int
    description: str | None = None
    game_data: dict[str, Any] | list[Any] | None = None



class FreeGameUpdate(BaseModel):
    title: str | None = Field(
        default=None,
        min_length=1,
        max_length=200,
    )

    description: str | None = None

    game_data: dict[str, Any] | list[Any] | None = None

    is_published: bool | None = None

    


class FreeGameUserResponse(BaseModel):
    id: int
    full_name: str
    username: str


class FreeGameResponse(BaseModel):
    id: int
    user_id: int
    title: str
    week: str
    description: str | None
    game_data: dict[str, Any] | list[Any] | None
    is_published: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime
    user: FreeGameUserResponse

    model_config = ConfigDict(
        from_attributes=True,
    )