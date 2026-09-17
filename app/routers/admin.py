from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.permissions import require_admin
from app.models.membership import Membership, MembershipPlan
from datetime import datetime, timedelta, timezone
from app.models.user import User
from app.core.membership_service import activate_membership_from_order
from app.models.membership_order import MembershipOrder
from app.schemas.admin import MembershipDeactivateRequest
from datetime import datetime, timezone

from app.schemas.admin import (
    AdminUserResponse,
    AdminUserStatusUpdate,
    MembershipDeactivateRequest,
)

from app.schemas.membership import (
    MembershipCreate,
    MembershipPlanCreate,
    MembershipPlanResponse,
    MembershipPlanUpdate,
    MembershipResponse,
    MembershipUpdate,
)


router = APIRouter(
    prefix="/admin",
    tags=["Admin"],
)


# ---------------------------------------------------------
# USERS
# ---------------------------------------------------------

@router.get(
    "/users",
    response_model=list[AdminUserResponse],
)
def get_all_users(
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    users = db.scalars(
        select(User)
        .order_by(User.id.desc())
    ).all()

    return users


@router.get(
    "/users/{user_id}",
    response_model=AdminUserResponse,
)
def get_user(
    user_id: int,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    user = db.get(User, user_id)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return user


@router.put(
    "/users/{user_id}/status",
    response_model=AdminUserResponse,
)
def update_user_status(
    user_id: int,
    data: AdminUserStatusUpdate,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    user = db.get(User, user_id)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Never allow the administrator to accidentally
    # deactivate or remove their own admin privileges.
    if user.id == admin.id:
        if data.is_active is False:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The administrator cannot deactivate their own account",
            )

    if data.is_active is not None:
        user.is_active = data.is_active

    if data.is_verified is not None:
        user.is_verified = data.is_verified

    db.commit()
    db.refresh(user)

    return user


# ---------------------------------------------------------
# MEMBERSHIP PLANS
# ---------------------------------------------------------

@router.get(
    "/membership-plans",
    response_model=list[MembershipPlanResponse],
)
def get_all_membership_plans(
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    plans = db.scalars(
        select(MembershipPlan)
        .order_by(MembershipPlan.id)
    ).all()

    return plans


@router.post(
    "/membership-plans",
    response_model=MembershipPlanResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_membership_plan(
    data: MembershipPlanCreate,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    if data.duration_type not in {"monthly", "yearly", "quarterly", "6 months"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Duration type must be monthly or yearly",
        )

    if data.price < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Price cannot be negative",
        )

    existing_plan = db.scalar(
        select(MembershipPlan)
        .where(MembershipPlan.name == data.name)
    )

    if existing_plan:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Membership plan name already exists",
        )

    plan = MembershipPlan(
        name=data.name,
        duration_type=data.duration_type,
        price=data.price,
        description=data.description,
        is_active=data.is_active,
    )

    db.add(plan)
    db.commit()
    db.refresh(plan)

    return plan


@router.put(
    "/membership-plans/{plan_id}",
    response_model=MembershipPlanResponse,
)
def update_membership_plan(
    plan_id: int,
    data: MembershipPlanUpdate,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    plan = db.get(MembershipPlan, plan_id)

    if plan is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Membership plan not found",
        )

    if data.duration_type is not None:
        if data.duration_type not in {"monthly", "yearly", "quarterly", "6 months"}:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Duration type must be monthly or yearly",
            )

        plan.duration_type = data.duration_type

    if data.name is not None:
        existing_plan = db.scalar(
            select(MembershipPlan)
            .where(
                MembershipPlan.name == data.name,
                MembershipPlan.id != plan_id,
            )
        )

        if existing_plan:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Membership plan name already exists",
            )

        plan.name = data.name

    if data.price is not None:
        if data.price < 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Price cannot be negative",
            )

        plan.price = data.price

    if data.description is not None:
        plan.description = data.description

    if data.is_active is not None:
        plan.is_active = data.is_active

    db.commit()
    db.refresh(plan)

    return plan


@router.delete(
    "/membership-plans/{plan_id}",
)
def delete_membership_plan(
    plan_id: int,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    plan = db.get(MembershipPlan, plan_id)

    if plan is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Membership plan not found",
        )

    # Do not physically delete a plan that is already
    # being used by a membership record.
    existing_membership = db.scalar(
        select(Membership)
        .where(Membership.plan_id == plan_id)
        .limit(1)
    )

    if existing_membership:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "This membership plan cannot be deleted because "
                "it is already assigned to a membership. "
                "Deactivate the plan instead."
            ),
        )

    db.delete(plan)
    db.commit()

    return {
        "message": "Membership plan deleted successfully",
        "plan_id": plan_id,
    }



# ---------------------------------------------------------
# MEMBERSHIPS
# ---------------------------------------------------------

@router.get(
    "/memberships",
    response_model=list[MembershipResponse],
)
def get_all_memberships(
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    memberships = db.scalars(
        select(Membership)
        .order_by(Membership.id.desc())
    ).all()

    return memberships


@router.post(
    "/memberships",
    response_model=MembershipResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_membership(
    data: MembershipCreate,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    # ---------------------------------------------------------
    # CHECK THAT THE USER EXISTS
    # ---------------------------------------------------------

    user = db.get(User, data.user_id)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # ---------------------------------------------------------
    # CHECK THAT THE MEMBERSHIP PLAN EXISTS
    # ---------------------------------------------------------

    plan = db.get(MembershipPlan, data.plan_id)

    if plan is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Membership plan not found",
        )

    # ---------------------------------------------------------
    # DO NOT ALLOW INACTIVE PLANS
    # ---------------------------------------------------------

    if not plan.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This membership plan is inactive",
        )

    # ---------------------------------------------------------
    # CHECK FOR EXISTING ACTIVE MEMBERSHIP
    # ---------------------------------------------------------

    existing_active_membership = db.scalar(
        select(Membership)
        .where(
            Membership.user_id == data.user_id,
            Membership.status == "active",
        )
        .order_by(Membership.end_date.desc())
    )

    if existing_active_membership is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "This user already has an active membership. "
                "Use the membership change process instead."
            ),
        )

    # ---------------------------------------------------------
    # SUPPORTED MEMBERSHIP DURATIONS
    # ---------------------------------------------------------

    duration_days = {
        "monthly": 30,
        "quarterly": 90,
        "6 months": 180,
        "yearly": 365,
    }

    days = duration_days.get(
        plan.duration_type.lower()
    )

    if days is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Invalid membership duration. "
                "Use monthly, quarterly, 6 months, or yearly."
            ),
        )

    # ---------------------------------------------------------
    # START DATE
    # ---------------------------------------------------------

    start_date = (
        data.start_date
        or datetime.now(timezone.utc)
    )

    # ---------------------------------------------------------
    # CALCULATE END DATE FROM THE PLAN
    # ---------------------------------------------------------

    end_date = start_date + timedelta(days=days)

    # ---------------------------------------------------------
    # CREATE MEMBERSHIP
    # ---------------------------------------------------------

    membership = Membership(
        user_id=data.user_id,
        plan_id=data.plan_id,
        start_date=start_date,
        end_date=end_date,
        status="active",
    )

    db.add(membership)
    db.commit()
    db.refresh(membership)

    return membership




@router.put(
    "/memberships/{membership_id}",
    response_model=MembershipResponse,
)
def update_membership(
    membership_id: int,
    data: MembershipUpdate,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    membership = db.get(Membership, membership_id)

    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Membership not found",
        )

    if data.plan_id is not None:
        plan = db.get(MembershipPlan, data.plan_id)

        if plan is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Membership plan not found",
            )

        membership.plan_id = data.plan_id

    if data.start_date is not None:
        membership.start_date = data.start_date

    if data.end_date is not None:
        membership.end_date = data.end_date

    if (
        membership.end_date <= membership.start_date
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="End date must be after start date",
        )

    if data.status is not None:
        if data.status not in {
            "active",
            "expired",
            "cancelled",
            "pending",
        }:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid membership status",
            )

        membership.status = data.status

    db.commit()
    db.refresh(membership)

    return membership


@router.delete(
    "/memberships/{membership_id}",
)
def delete_membership(
    membership_id: int,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    membership = db.get(Membership, membership_id)

    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Membership not found",
        )

    db.delete(membership)
    db.commit()

    return {
        "message": "Membership deleted successfully",
        "membership_id": membership_id,
    }



# ---------------------------------------------------------
# MEMBERSHIP ORDERS
# ---------------------------------------------------------

@router.get(
    "/membership-orders",
)
def get_membership_orders(
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    orders = db.scalars(
        select(MembershipOrder)
        .order_by(
            MembershipOrder.created_at.desc()
        )
    ).all()

    return orders


# ---------------------------------------------------------
# PENDING MEMBERSHIP ORDERS
# ---------------------------------------------------------

@router.get(
    "/membership-orders/pending",
)
def get_pending_membership_orders(
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    orders = db.scalars(
        select(MembershipOrder)
        .where(
            MembershipOrder.status == "pending"
        )
        .order_by(
            MembershipOrder.created_at.asc()
        )
    ).all()

    return {
        "count": len(orders),
        "orders": orders,
    }


# ---------------------------------------------------------
# APPROVE MEMBERSHIP ORDER
# ---------------------------------------------------------

@router.post(
    "/membership-orders/{order_id}/approve",
)
def approve_membership_order(
    order_id: int,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    # -----------------------------------------------------
    # FIND ORDER
    # -----------------------------------------------------

    order = db.get(
        MembershipOrder,
        order_id,
    )

    if order is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Membership order not found",
        )

    # -----------------------------------------------------
    # ONLY PENDING ORDERS CAN BE APPROVED
    # -----------------------------------------------------

    if order.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"This membership order has already been "
                f"{order.status}."
            ),
        )

    try:
        # -------------------------------------------------
        # MARK ORDER AS PAID
        # -------------------------------------------------

        order.status = "paid"
        order.paid_at = datetime.now(timezone.utc)

        # -------------------------------------------------
        # ACTIVATE MEMBERSHIP
        # -------------------------------------------------

        membership = activate_membership_from_order(
            db,
            order,
        )

        # -------------------------------------------------
        # COMMIT EVERYTHING TOGETHER
        # -------------------------------------------------

        db.commit()

        db.refresh(order)
        db.refresh(membership)

    except Exception:
        db.rollback()
        raise

    return {
        "message": "Membership order approved successfully",
        "order_id": order.id,
        "membership_id": membership.id,
        "order_status": order.status,
        "membership_status": membership.status,
    }


# ---------------------------------------------------------
# REJECT MEMBERSHIP ORDER
# ---------------------------------------------------------

@router.post(
    "/membership-orders/{order_id}/reject",
)
def reject_membership_order(
    order_id: int,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    # -----------------------------------------------------
    # FIND ORDER
    # -----------------------------------------------------

    order = db.get(
        MembershipOrder,
        order_id,
    )

    if order is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Membership order not found",
        )

    # -----------------------------------------------------
    # ONLY PENDING ORDERS CAN BE REJECTED
    # -----------------------------------------------------

    if order.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"This membership order has already been "
                f"{order.status}."
            ),
        )

    # -----------------------------------------------------
    # CANCEL ORDER
    # -----------------------------------------------------

    order.status = "cancelled"

    db.commit()

    return {
        "message": "Membership order rejected",
        "order_id": order.id,
        "status": order.status,
    }




@router.post("/memberships/{membership_id}/deactivate")
def deactivate_membership(
    membership_id: int,
    data: MembershipDeactivateRequest,
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    membership = db.get(Membership, membership_id)

    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Membership not found",
        )

    if membership.status != "active":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"This membership cannot be deactivated because "
                f"its current status is '{membership.status}'."
            ),
        )

    # Deactivate the membership
    membership.status = "deactivated"

    # Store when the membership was deactivated
    membership.deactivated_at = datetime.now(timezone.utc)

    # Store the reason given by the administrator
    membership.deactivation_reason = data.reason

    # Store which administrator performed the action
    membership.deactivated_by = current_admin.id

    db.commit()
    db.refresh(membership)

    return {
        "message": "Membership deactivated successfully",
        "membership_id": membership.id,
        "user_id": membership.user_id,
        "status": membership.status,
        "deactivated_at": membership.deactivated_at,
        "deactivation_reason": membership.deactivation_reason,
        "deactivated_by": membership.deactivated_by,
    }