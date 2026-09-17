from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.membership import Membership
from app.models.membership_order import MembershipOrder


MEMBERSHIP_DURATION_DAYS = {
    "monthly": 30,
    "quarterly": 90,
    "6 months": 180,
    "yearly": 365,
}


def activate_membership_from_order(
    db: Session,
    order: MembershipOrder,
):
    # -----------------------------------------------------
    # ORDER MUST ALREADY BE MARKED AS PAID
    # -----------------------------------------------------

    if order.status != "paid":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Membership order has not been paid",
        )

    # -----------------------------------------------------
    # GET THE PLAN
    # -----------------------------------------------------

    plan = order.plan

    if plan is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Membership plan no longer exists",
        )

    # -----------------------------------------------------
    # GET PLAN DURATION
    # -----------------------------------------------------

    duration_days = MEMBERSHIP_DURATION_DAYS.get(
        plan.duration_type.lower()
    )

    if duration_days is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid membership duration",
        )

    # -----------------------------------------------------
    # CURRENT TIME
    # -----------------------------------------------------

    now = datetime.now(timezone.utc)

    # -----------------------------------------------------
    # FIND CURRENT ACTIVE MEMBERSHIP
    # -----------------------------------------------------

    current_membership = (
        db.query(Membership)
        .filter(
            Membership.user_id == order.user_id,
            Membership.status == "active",
        )
        .order_by(
            Membership.end_date.desc()
        )
        .first()
    )

    # -----------------------------------------------------
    # HANDLE EXISTING MEMBERSHIP
    # -----------------------------------------------------

    if current_membership is not None:

        # -------------------------------------------------
        # SAME PLAN CANNOT BE ACTIVATED AGAIN
        # -------------------------------------------------

        if current_membership.plan_id == order.plan_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "The user already has this membership "
                    "plan active."
                ),
            )

        # -------------------------------------------------
        # DIFFERENT PLAN = PLAN CHANGE
        # -------------------------------------------------

        current_membership.status = "changed_plan"

    # -----------------------------------------------------
    # CALCULATE NEW MEMBERSHIP END DATE
    # -----------------------------------------------------

    end_date = now + timedelta(
        days=duration_days
    )

    # -----------------------------------------------------
    # CREATE NEW ACTIVE MEMBERSHIP
    # -----------------------------------------------------

    new_membership = Membership(
        user_id=order.user_id,
        plan_id=order.plan_id,
        start_date=now,
        end_date=end_date,
        status="active",
    )

    db.add(new_membership)

    # -----------------------------------------------------
    # IMPORTANT
    #
    # DO NOT COMMIT HERE.
    #
    # The admin approval endpoint controls the entire
    # transaction.
    # -----------------------------------------------------

    return new_membership