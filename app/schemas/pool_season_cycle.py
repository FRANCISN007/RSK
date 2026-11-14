
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class PoolSeasonCycleCreate(BaseModel):
    name: str = Field(min_length=4, max_length=20)

    english_season_id: int
    aussie_season_id: int

    english_start_date: date
    english_end_date: date

    aussie_start_date: date
    aussie_end_date: date

    is_active: bool = True

    @model_validator(mode="after")
    def validate_cycle_dates(self):
        if self.english_season_id == self.aussie_season_id:
            raise ValueError(
                "English and Aussie must be different seasons."
            )

        if self.english_start_date > self.english_end_date:
            raise ValueError(
                "English start date must not be after its end date."
            )

        if self.aussie_start_date > self.aussie_end_date:
            raise ValueError(
                "Aussie start date must not be after its end date."
            )

        if self.aussie_start_date <= self.english_end_date:
            raise ValueError(
                "Aussie must start after the English season ends."
            )

        return self


class PoolSeasonCycleUpdate(BaseModel):
    english_start_date: date | None = None
    english_end_date: date | None = None
    aussie_start_date: date | None = None
    aussie_end_date: date | None = None
    is_active: bool | None = None


class PoolSeasonCycleResponse(BaseModel):
    id: int
    name: str

    english_season_id: int
    aussie_season_id: int

    english_start_date: date
    english_end_date: date

    aussie_start_date: date
    aussie_end_date: date

    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
