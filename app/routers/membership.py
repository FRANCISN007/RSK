from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import get_current_user
from app.models.membership import Membership, MembershipPlan
from app.models.membership_order import MembershipOrder
from app.models.user import User
from app.schemas.membership import (
    MembershipOrderCreate,
    MembershipOrderResponse,
    MembershipPlanResponse,
    MembershipResponse,
)

from sqlalchemy.orm import Session, joinedload

router = APIRouter(
    prefix="/memberships",
    tags=["Memberships"],
)


MEMBERSHIP_DURATION_DAYS = {
    "monthly": 30,
    "quarterly": 90,
    "6 months": 180,
    "yearly": 365,
}


# ---------------------------------------------------------
# AVAILABLE PLANS
# ---------------------------------------------------------

@router.get(
    "/plans",
    response_model=list[MembershipPlanResponse],
)
def get_membership_plans(
    db: Session = Depends(get_db),
):
    plans = db.scalars(
        select(MembershipPlan)
        .where(
            MembershipPlan.is_active.is_(True)
        )
        .order_by(MembershipPlan.id)
    ).all()

    return plans


# ---------------------------------------------------------
# CURRENT USER MEMBERSHIP
# ---------------------------------------------------------

@router.get(
    "/status",
    response_model=MembershipResponse | None,
)
def get_my_membership(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    now = datetime.now(timezone.utc)

    membership = db.scalar(
        select(Membership)
        .options(
            joinedload(Membership.plan)
        )
        .where(
            Membership.user_id == current_user.id,
            Membership.status == "active",
        )
        .order_by(Membership.end_date.desc())
    )

    if membership is None:
        return None

    if membership.end_date <= now:
        membership.status = "expired"
        db.commit()
        return None

    return membership


# ---------------------------------------------------------
# CREATE MEMBERSHIP ORDER
# ---------------------------------------------------------

@router.post(
    "/orders",
    response_model=MembershipOrderResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_membership_order(
    data: MembershipOrderCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # -----------------------------------------------------
    # CHECK THAT THE PLAN EXISTS
    # -----------------------------------------------------

    plan = db.get(
        MembershipPlan,
        data.plan_id,
    )

    if plan is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Membership plan not found",
        )

    # -----------------------------------------------------
    # CHECK THAT THE PLAN IS ACTIVE
    # -----------------------------------------------------

    if not plan.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This membership plan is inactive",
        )

    # -----------------------------------------------------
    # VALIDATE PLAN DURATION
    # -----------------------------------------------------

    duration_days = MEMBERSHIP_DURATION_DAYS.get(
        plan.duration_type.lower()
    )

    if duration_days is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Invalid membership duration. "
                "Use monthly, quarterly, 6 months, or yearly."
            ),
        )

    # -----------------------------------------------------
    # CHECK CURRENT ACTIVE MEMBERSHIP
    # -----------------------------------------------------

    current_membership = db.scalar(
        select(Membership)
        .where(
            Membership.user_id == current_user.id,
            Membership.status == "active",
        )
        .order_by(
            Membership.end_date.desc()
        )
    )

    if current_membership is not None:

        # -------------------------------------------------
        # USER ALREADY HAS THIS EXACT PLAN
        # -------------------------------------------------

        if current_membership.plan_id == plan.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "You already have this membership plan active."
                ),
            )

    # -----------------------------------------------------
    # CHECK FOR EXISTING PENDING ORDER
    # -----------------------------------------------------

    pending_order = db.scalar(
        select(MembershipOrder)
        .where(
            MembershipOrder.user_id == current_user.id,
            MembershipOrder.status == "pending",
        )
        .order_by(
            MembershipOrder.created_at.desc()
        )
    )

    if pending_order is not None:

        # -------------------------------------------------
        # SAME PLAN ALREADY PENDING
        # -------------------------------------------------

        if pending_order.plan_id == plan.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "You already have a pending order "
                    "for this membership plan."
                ),
            )

        # -------------------------------------------------
        # ANOTHER PLAN IS ALREADY PENDING
        # -------------------------------------------------

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "You already have a pending membership order. "
                "Complete or cancel that order before creating "
                "another one."
            ),
        )

    # -----------------------------------------------------
    # CREATE ORDER
    # -----------------------------------------------------

    order = MembershipOrder(
        user_id=current_user.id,
        plan_id=plan.id,

        # IMPORTANT:
        # Save the current price into the order.
        #
        # If the administrator changes the plan price later,
        # this order will still keep the original amount.
        amount=plan.price,

        status="pending",
    )

    db.add(order)

    db.commit()
    db.refresh(order)

    return order


# ---------------------------------------------------------
# MY MEMBERSHIP ORDERS
# ---------------------------------------------------------

@router.get(
    "/orders",
    response_model=list[MembershipOrderResponse],
)
def get_my_membership_orders(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    orders = db.scalars(
        select(MembershipOrder)
        .where(
            MembershipOrder.user_id == current_user.id
        )
        .order_by(
            MembershipOrder.created_at.desc()
        )
    ).all()

    return orders