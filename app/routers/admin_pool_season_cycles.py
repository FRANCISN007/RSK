from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.dependencies.auth import require_admin
from app.models.pool_season import PoolSeason
from app.models.pool_season_cycle import PoolSeasonCycle
from app.models.pool_week import PoolWeek
from app.models.user import User
from app.schemas.pool_season_cycle import (
    PoolSeasonCycleCreate,
    PoolSeasonCycleResponse,
    PoolSeasonCycleUpdate,
)
from app.services.pool_schedule import build_pool_cycle_schedule


router = APIRouter(
    prefix="/admin_pool_season_cycles",
    tags=["Admin Pool Season Cycles"],
)


def get_cycle_or_404(db: Session, cycle_id: int) -> PoolSeasonCycle:
    cycle = db.scalar(
        select(PoolSeasonCycle)
        .options(
            joinedload(PoolSeasonCycle.english_season),
            joinedload(PoolSeasonCycle.aussie_season),
        )
        .where(PoolSeasonCycle.id == cycle_id)
    )
    if cycle is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pool season cycle not found.",
        )
    return cycle


def validate_seasons(
    db: Session,
    english_season_id: int,
    aussie_season_id: int,
) -> tuple[PoolSeason, PoolSeason]:
    if english_season_id == aussie_season_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="English and Aussie must be different seasons.",
        )

    english = db.get(PoolSeason, english_season_id)
    aussie = db.get(PoolSeason, aussie_season_id)

    if english is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="English pool season not found.",
        )
    if aussie is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Aussie pool season not found.",
        )
    return english, aussie


def build_preview_cycle(
    *,
    name: str,
    english_season: PoolSeason,
    aussie_season: PoolSeason,
    english_start_date: date,
    english_end_date: date,
    aussie_start_date: date,
    aussie_end_date: date,
    is_active: bool = True,
) -> PoolSeasonCycle:
    """Build an unsaved cycle for schedule validation and preview."""
    return PoolSeasonCycle(
        name=name,
        english_season_id=english_season.id,
        aussie_season_id=aussie_season.id,
        english_start_date=english_start_date,
        english_end_date=english_end_date,
        aussie_start_date=aussie_start_date,
        aussie_end_date=aussie_end_date,
        is_active=is_active,
        english_season=english_season,
        aussie_season=aussie_season,
    )


def preview_response(schedule: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "total_weeks": len(schedule),
        "weeks": [
            {
                "season_id": item["season_id"],
                "season_name": item["season_name"],
                "year": item["year"],
                "week_number": item["week_number"],
                "closing_date": item["closing_date"],
                "closes_at": item["closes_at"],
            }
            for item in schedule
        ],
    }


def find_existing_season_week(
    db: Session,
    item: dict[str, Any],
) -> PoolWeek | None:
    """Find a row matching the database's season/year/week unique key."""
    return db.scalar(
        select(PoolWeek).where(
            PoolWeek.season_id == item["season_id"],
            PoolWeek.year == item["year"],
            PoolWeek.week_number == item["week_number"],
        )
    )


def describe_existing_week(week: PoolWeek) -> dict[str, Any]:
    return {
        "existing_pool_week_id": week.id,
        "existing_cycle_id": week.cycle_id,
        "existing_season_id": week.season_id,
        "existing_year": week.year,
        "existing_week_number": week.week_number,
        "existing_closes_at": (
            week.closes_at.isoformat() if week.closes_at is not None else None
        ),
    }


def get_schedule_conflicts(
    db: Session,
    cycle: PoolSeasonCycle,
    schedule: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[PoolWeek], int]:
    """
    Inspect the whole schedule before generation.

    Returns:
      - every conflict found,
      - newly created PoolWeek objects (not yet added to the session),
      - number of already-generated weeks skipped.
    """
    conflicts: list[dict[str, Any]] = []
    weeks_to_create: list[PoolWeek] = []
    skipped_existing = 0

    existing_cycle_weeks = db.scalars(
        select(PoolWeek).where(PoolWeek.cycle_id == cycle.id)
    ).all()
    cycle_weeks_by_number = {week.week_number: week for week in existing_cycle_weeks}

    for item in schedule:
        week_number = item["week_number"]
        linked_week = cycle_weeks_by_number.get(week_number)

        if linked_week is not None:
            # A cycle/week-number row must also match the intended season/year.
            if (
                linked_week.season_id != item["season_id"]
                or linked_week.year != item["year"]
            ):
                conflicts.append(
                    {
                        "week_number": week_number,
                        "reason": "cycle_week_identity_mismatch",
                        "message": (
                            "A week is already linked to this cycle with a "
                            "different season or year. It was not changed."
                        ),
                        **describe_existing_week(linked_week),
                    }
                )
            else:
                # Never replace its saved cutoff, even if cycle dates changed.
                skipped_existing += 1
            continue

        existing = find_existing_season_week(db, item)
        if existing is not None:
            conflicts.append(
                {
                    "week_number": week_number,
                    "season_id": item["season_id"],
                    "year": item["year"],
                    "reason": (
                        "already_linked_to_another_cycle"
                        if existing.cycle_id is not None
                        else "legacy_week_exists"
                    ),
                    "message": (
                        "A matching pool week already exists. Review it and "
                        "link it explicitly if appropriate; it will not be "
                        "overwritten or linked automatically."
                    ),
                    **describe_existing_week(existing),
                }
            )
            continue

        weeks_to_create.append(
            PoolWeek(
                cycle_id=cycle.id,
                season_id=item["season_id"],
                year=item["year"],
                week_number=week_number,
                closes_at=item["closes_at"],
            )
        )

    return conflicts, weeks_to_create, skipped_existing


@router.post("/preview")
def preview_new_cycle(
    data: PoolSeasonCycleCreate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Preview a proposed cycle and identify existing-week conflicts."""
    existing = db.scalar(
        select(PoolSeasonCycle).where(PoolSeasonCycle.name == data.name)
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A cycle with that name already exists.",
        )

    english, aussie = validate_seasons(
        db, data.english_season_id, data.aussie_season_id
    )
    cycle = build_preview_cycle(
        name=data.name,
        english_season=english,
        aussie_season=aussie,
        english_start_date=data.english_start_date,
        english_end_date=data.english_end_date,
        aussie_start_date=data.aussie_start_date,
        aussie_end_date=data.aussie_end_date,
        is_active=data.is_active,
    )
    schedule = build_pool_cycle_schedule(cycle)
    preview = preview_response(schedule)

    conflicts = []
    for index, item in enumerate(schedule):
        existing_week = find_existing_season_week(db, item)
        if existing_week is None:
            item_status = "will_create"
        else:
            item_status = (
                "already_linked_to_cycle"
                if existing_week.cycle_id is not None
                else "legacy_week_conflict"
            )
            conflicts.append(
                {
                    "week_number": item["week_number"],
                    "season_id": item["season_id"],
                    "year": item["year"],
                    "reason": item_status,
                    **describe_existing_week(existing_week),
                }
            )
        preview["weeks"][index]["status"] = item_status

    preview["conflicts"] = conflicts
    preview["conflict_count"] = len(conflicts)
    preview["can_generate_without_review"] = not conflicts
    return preview


@router.post(
    "",
    response_model=PoolSeasonCycleResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_pool_season_cycle(
    data: PoolSeasonCycleCreate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Save cycle configuration only. Week creation uses the generate endpoint."""
    existing = db.scalar(
        select(PoolSeasonCycle).where(PoolSeasonCycle.name == data.name)
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A cycle with that name already exists.",
        )

    english, aussie = validate_seasons(
        db, data.english_season_id, data.aussie_season_id
    )
    cycle = build_preview_cycle(
        name=data.name,
        english_season=english,
        aussie_season=aussie,
        english_start_date=data.english_start_date,
        english_end_date=data.english_end_date,
        aussie_start_date=data.aussie_start_date,
        aussie_end_date=data.aussie_end_date,
        is_active=data.is_active,
    )
    build_pool_cycle_schedule(cycle)

    db.add(cycle)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The cycle could not be created because of a database conflict.",
        )
    db.refresh(cycle)
    return cycle


@router.get("", response_model=list[PoolSeasonCycleResponse])
def get_pool_season_cycles(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return db.scalars(
        select(PoolSeasonCycle).order_by(PoolSeasonCycle.id.desc())
    ).all()


@router.get("/{cycle_id}", response_model=PoolSeasonCycleResponse)
def get_pool_season_cycle(
    cycle_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return get_cycle_or_404(db, cycle_id)


@router.get("/{cycle_id}/preview")
def preview_existing_cycle(
    cycle_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    cycle = get_cycle_or_404(db, cycle_id)
    schedule = build_pool_cycle_schedule(cycle)
    preview = preview_response(schedule)

    conflicts, _weeks_to_create, skipped_existing = get_schedule_conflicts(
        db, cycle, schedule
    )
    existing_cycle_weeks = db.scalars(
        select(PoolWeek).where(PoolWeek.cycle_id == cycle_id)
    ).all()
    existing_by_number = {week.week_number: week for week in existing_cycle_weeks}

    for index, item in enumerate(schedule):
        saved_week = existing_by_number.get(item["week_number"])
        if saved_week is not None:
            preview["weeks"][index]["status"] = (
                "already_generated"
                if (
                    saved_week.season_id == item["season_id"]
                    and saved_week.year == item["year"]
                )
                else "cycle_week_identity_mismatch"
            )
            preview["weeks"][index]["saved_pool_week_id"] = saved_week.id
            preview["weeks"][index]["saved_closes_at"] = saved_week.closes_at
            preview["weeks"][index]["saved_season_id"] = saved_week.season_id
            preview["weeks"][index]["saved_year"] = saved_week.year
        else:
            existing = find_existing_season_week(db, item)
            if existing is not None:
                preview["weeks"][index]["status"] = (
                    "legacy_week_conflict"
                    if existing.cycle_id is None
                    else "already_linked_to_another_cycle"
                )
                preview["weeks"][index].update(describe_existing_week(existing))
            else:
                preview["weeks"][index]["status"] = "will_create"

    preview["generated_weeks"] = len(existing_cycle_weeks)
    preview["new_weeks"] = sum(
        1 for item in preview["weeks"] if item["status"] == "will_create"
    )
    preview["conflicts"] = conflicts
    preview["conflict_count"] = len(conflicts)
    preview["can_generate"] = not conflicts
    preview["skipped_existing"] = skipped_existing
    return preview


@router.put("/{cycle_id}", response_model=PoolSeasonCycleResponse)
def update_pool_season_cycle(
    cycle_id: int,
    data: PoolSeasonCycleUpdate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Update cycle configuration. Existing PoolWeek.closes_at values are never
    recalculated or rewritten by this endpoint.
    """
    cycle = get_cycle_or_404(db, cycle_id)
    proposed = {
        "english_start_date": (
            data.english_start_date
            if data.english_start_date is not None
            else cycle.english_start_date
        ),
        "english_end_date": (
            data.english_end_date
            if data.english_end_date is not None
            else cycle.english_end_date
        ),
        "aussie_start_date": (
            data.aussie_start_date
            if data.aussie_start_date is not None
            else cycle.aussie_start_date
        ),
        "aussie_end_date": (
            data.aussie_end_date
            if data.aussie_end_date is not None
            else cycle.aussie_end_date
        ),
    }

    candidate = build_preview_cycle(
        name=cycle.name,
        english_season=cycle.english_season,
        aussie_season=cycle.aussie_season,
        english_start_date=proposed["english_start_date"],
        english_end_date=proposed["english_end_date"],
        aussie_start_date=proposed["aussie_start_date"],
        aussie_end_date=proposed["aussie_end_date"],
        is_active=(
            data.is_active if data.is_active is not None else cycle.is_active
        ),
    )
    build_pool_cycle_schedule(candidate)

    for field, value in proposed.items():
        setattr(cycle, field, value)
    if data.is_active is not None:
        cycle.is_active = data.is_active

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The cycle could not be updated because of a database conflict.",
        )
    db.refresh(cycle)
    return cycle


@router.post("/{cycle_id}/generate")
def generate_pool_weeks(
    cycle_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Validate the entire schedule first. If any conflict exists, create no weeks.
    Existing rows and saved deadlines are never overwritten.
    """
    cycle = get_cycle_or_404(db, cycle_id)
    if not cycle.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Activate this cycle before generating its weeks.",
        )

    schedule = build_pool_cycle_schedule(cycle)
    conflicts, weeks_to_create, skipped_existing = get_schedule_conflicts(
        db, cycle, schedule
    )

    if conflicts:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": (
                    "Week generation was stopped because conflicts need admin "
                    "review. No new weeks were created."
                ),
                "cycle_id": cycle.id,
                "conflict_count": len(conflicts),
                "conflicts": conflicts,
                "instruction": (
                    "Review each existing week. Use the explicit link endpoint "
                    "only when the existing row is the correct week."
                ),
            },
        )

    if not weeks_to_create:
        return {
            "message": "All scheduled weeks have already been generated.",
            "cycle_id": cycle.id,
            "created": 0,
            "skipped_existing": skipped_existing,
        }

    db.add_all(weeks_to_create)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Week generation encountered a database conflict. "
                "The transaction was rolled back; no weeks from this request "
                "were committed."
            ),
        )

    return {
        "message": "Pool weeks generated successfully.",
        "cycle_id": cycle.id,
        "created": len(weeks_to_create),
        "skipped_existing": skipped_existing,
    }


@router.post("/{cycle_id}/link-existing-week/{pool_week_id}")
def link_existing_pool_week(
    cycle_id: int,
    pool_week_id: int,
    confirm_deadline_difference: bool = False,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Explicitly link a matching legacy week to a cycle.

    Only cycle_id is changed. The existing week deadline and all other fields
    remain untouched. If its deadline differs from the current calculated
    schedule, the admin must explicitly confirm that difference.
    """
    cycle = get_cycle_or_404(db, cycle_id)
    pool_week = db.get(PoolWeek, pool_week_id)
    if pool_week is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pool week not found.",
        )

    if pool_week.cycle_id == cycle.id:
        return {
            "message": "This pool week is already linked to this cycle.",
            "cycle_id": cycle.id,
            "pool_week_id": pool_week.id,
            "closes_at": pool_week.closes_at,
            "changed": False,
        }

    if pool_week.cycle_id is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": "This pool week is already linked to another cycle.",
                **describe_existing_week(pool_week),
            },
        )

    schedule = build_pool_cycle_schedule(cycle)
    target = next(
        (
            item
            for item in schedule
            if item["week_number"] == pool_week.week_number
        ),
        None,
    )
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "This pool week's number is not part of the selected cycle's "
                "current schedule."
            ),
        )

    if (
        pool_week.season_id != target["season_id"]
        or pool_week.year != target["year"]
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": (
                    "The existing pool week does not match the season and year "
                    "for this cycle week number. It was not changed."
                ),
                "expected_season_id": target["season_id"],
                "expected_year": target["year"],
                **describe_existing_week(pool_week),
            },
        )

    # Guard against an unexpected existing row under the cycle/week unique key.
    cycle_week = db.scalar(
        select(PoolWeek).where(
            PoolWeek.cycle_id == cycle.id,
            PoolWeek.week_number == pool_week.week_number,
            PoolWeek.id != pool_week.id,
        )
    )
    if cycle_week is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": "Another pool week already uses this cycle week number.",
                **describe_existing_week(cycle_week),
            },
        )

    deadline_matches = pool_week.closes_at == target["closes_at"]
    if not deadline_matches and not confirm_deadline_difference:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": (
                    "The saved deadline differs from the current schedule. "
                    "The deadline will be preserved; repeat the request with "
                    "confirm_deadline_difference=true only after reviewing it."
                ),
                "saved_closes_at": (
                    pool_week.closes_at.isoformat()
                    if pool_week.closes_at is not None
                    else None
                ),
                "scheduled_closes_at": (
                    target["closes_at"].isoformat()
                    if target["closes_at"] is not None
                    else None
                ),
                "pool_week_id": pool_week.id,
                "cycle_id": cycle.id,
            },
        )

    # Critical: linking must not modify the saved cutoff or any other field.
    pool_week.cycle_id = cycle.id
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "The pool week could not be linked because of a database "
                "conflict. No changes were committed."
            ),
        )

    db.refresh(pool_week)
    return {
        "message": "Existing pool week linked to the cycle.",
        "cycle_id": cycle.id,
        "pool_week_id": pool_week.id,
        "closes_at": pool_week.closes_at,
        "deadline_matches_current_schedule": deadline_matches,
        "deadline_preserved": True,
        "changed": True,
    }
