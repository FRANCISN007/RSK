from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.membership import Membership, MembershipPlan


MEMBERSHIP_DURATION_DAYS = {
    "monthly": 30,
    "quarterly": 90,
    "6 months": 180,
    "yearly": 365,
}


def activate_membership_from_order(
    db: Session,
    order,
) -> Membership:
    """
    Activate a new membership after an admin approves an order.

    If the user already has an active membership:
    - End it immediately.
    - Change its status to changed_plan.
    - Do not transfer unused days.

    The new membership starts immediately and receives
    the full duration of its selected plan.

    This function does not commit. The caller controls
    the transaction.
    """

    if order.status != "paid":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only paid membership orders can be activated.",
        )

    plan = db.scalar(
        select(MembershipPlan).where(
            MembershipPlan.id == order.plan_id
        )
    )

    if plan is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Membership plan not found.",
        )

    if not plan.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This membership plan is inactive.",
        )

    duration_type = (plan.duration_type or "").strip().lower()
    duration_days = MEMBERSHIP_DURATION_DAYS.get(duration_type)

    if duration_days is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Invalid membership duration. "
                "Use monthly, quarterly, 6 months, or yearly."
            ),
        )

    now = datetime.now(timezone.utc)

    # Lock the user's active membership while changing plans.
    current_membership = db.scalar(
        select(Membership)
        .where(
            Membership.user_id == order.user_id,
            Membership.status == "active",
        )
        .order_by(Membership.end_date.desc())
        .with_for_update()
    )

    if current_membership is not None:
        current_end_date = current_membership.end_date

        # Handle a database datetime that has no timezone.
        if current_end_date.tzinfo is None:
            current_end_date = current_end_date.replace(
                tzinfo=timezone.utc
            )

        if current_end_date <= now:
            current_membership.status = "expired"
        else:
            if current_membership.plan_id == order.plan_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        "The user already has an active membership "
                        "on this plan."
                    ),
                )

            # End the old membership immediately.
            # Unused days are not transferred.
            current_membership.status = "changed_plan"
            current_membership.end_date = now

    # Start the new membership immediately.
    new_membership = Membership(
        user_id=order.user_id,
        plan_id=order.plan_id,
        start_date=now,
        end_date=now + timedelta(days=duration_days),
        status="active",
    )

    db.add(new_membership)
    db.flush()

    return new_membership