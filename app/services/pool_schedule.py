
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status

from app.models.pool_season_cycle import PoolSeasonCycle


POOL_TIMEZONE = ZoneInfo("Africa/Lagos")


def first_closing_date(
    start_date: date,
    closing_weekday: int,
) -> date:
    """
    Find the first configured closing weekday on or after
    the season's start date.

    API weekday numbering: Monday=1 ... Sunday=7.
    """
    if not 1 <= closing_weekday <= 7:
        raise ValueError("closing_weekday must be between 1 and 7.")

    target_weekday = closing_weekday - 1
    days_until_closing = (
        target_weekday - start_date.weekday()
    ) % 7

    return start_date + timedelta(days=days_until_closing)


def closing_timestamp(
    closing_date: date,
    closing_time: time,
) -> datetime:
    """
    Interpret the cutoff in Africa/Lagos and return UTC
    for reliable storage and comparison.
    """
    local_time = closing_time.replace(tzinfo=None)

    local_datetime = datetime.combine(
        closing_date,
        local_time,
    ).replace(tzinfo=POOL_TIMEZONE)

    return local_datetime.astimezone(timezone.utc)


def season_closing_dates(
    start_date: date,
    end_date: date,
    closing_weekday: int,
) -> list[date]:
    if start_date > end_date:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Season start date must not be after its end date.",
        )

    current_date = first_closing_date(
        start_date,
        closing_weekday,
    )

    dates = []

    while current_date <= end_date:
        dates.append(current_date)
        current_date += timedelta(days=7)

    return dates


def build_pool_cycle_schedule(
    cycle: PoolSeasonCycle,
) -> list[dict]:
    """
    Build the proposed weeks for one cycle.

    Week numbering starts at 1 for English and continues
    through the Aussie season without resetting.

    This function only builds a preview. It does not write
    to the database or change existing weeks.
    """
    english = cycle.english_season
    aussie = cycle.aussie_season

    if english is None or aussie is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="The cycle must reference both seasons.",
        )

    if english.id == aussie.id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="English and Aussie must be different seasons.",
        )

    if cycle.english_start_date > cycle.english_end_date:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid English season date range.",
        )

    if cycle.aussie_start_date > cycle.aussie_end_date:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid Aussie season date range.",
        )

    if cycle.aussie_start_date <= cycle.english_end_date:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Aussie must start after English ends.",
        )

    english_dates = season_closing_dates(
        cycle.english_start_date,
        cycle.english_end_date,
        english.closing_weekday,
    )

    aussie_dates = season_closing_dates(
        cycle.aussie_start_date,
        cycle.aussie_end_date,
        aussie.closing_weekday,
    )

    if not english_dates:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="The English date range contains no closing day.",
        )

    if not aussie_dates:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="The Aussie date range contains no closing day.",
        )

    # Require the first Aussie cutoff to be the next configured
    # Friday after the final English Saturday cutoff, when those
    # are the season rules configured in the database.
    expected_aussie_start = (
        english_dates[-1] + timedelta(days=1)
    )
    expected_aussie_close = first_closing_date(
        expected_aussie_start,
        aussie.closing_weekday,
    )

    if aussie_dates[0] != expected_aussie_close:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "The Aussie date range must include the first "
                "Aussie closing day after the final English cutoff. "
                f"Expected {expected_aussie_close.isoformat()}."
            ),
        )

    schedule = []
    week_number = 1

    for season, closing_dates in (
        (english, english_dates),
        (aussie, aussie_dates),
    ):
        for closing_date in closing_dates:
            schedule.append(
                {
                    "season_id": season.id,
                    "season_name": season.name,
                    "year": closing_date.year,
                    "week_number": week_number,
                    "closing_date": closing_date,
                    "closes_at": closing_timestamp(
                        closing_date,
                        season.closing_time,
                    ),
                }
            )
            week_number += 1

    return schedule
