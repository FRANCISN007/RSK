from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class PoolWeekCreate(BaseModel):
    season_id: int

    year: int = Field(
        ge=2000,
        le=2100,
    )

    week_number: int = Field(
        ge=1,
        le=53,
    )


class PoolWeekResponse(BaseModel):
    id: int
    season_id: int
    year: int
    week_number: int
    closes_at: datetime
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
    )


    