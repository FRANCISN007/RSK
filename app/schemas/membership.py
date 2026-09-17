from datetime import datetime

from pydantic import BaseModel, ConfigDict


# =========================================================
# MEMBERSHIP PLANS
# =========================================================

class MembershipPlanCreate(BaseModel):
    name: str
    duration_type: str
    price: float
    description: str | None = None
    is_active: bool = True


class MembershipPlanUpdate(BaseModel):
    name: str | None = None
    duration_type: str | None = None
    price: float | None = None
    description: str | None = None
    is_active: bool | None = None


class MembershipPlanResponse(BaseModel):
    id: int
    name: str
    duration_type: str
    price: float
    description: str | None
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(
        from_attributes=True
    )


# =========================================================
# MEMBERSHIPS
# =========================================================

class MembershipCreate(BaseModel):
    user_id: int
    plan_id: int
    start_date: datetime | None = None
    status: str = "active"


class MembershipUpdate(BaseModel):
    plan_id: int | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None
    status: str | None = None


class MembershipResponse(BaseModel):
    id: int
    user_id: int
    plan_id: int
    start_date: datetime
    end_date: datetime
    status: str
    created_at: datetime

    # -----------------------------------------------------
    # DEACTIVATION INFORMATION
    # -----------------------------------------------------

    deactivated_at: datetime | None = None
    deactivation_reason: str | None = None
    deactivated_by: int | None = None

    model_config = ConfigDict(
        from_attributes=True
    )


# =========================================================
# MEMBERSHIP ORDERS
# =========================================================

class MembershipOrderCreate(BaseModel):
    plan_id: int


class MembershipOrderResponse(BaseModel):
    id: int
    user_id: int
    plan_id: int
    amount: float
    status: str
    created_at: datetime
    paid_at: datetime | None

    model_config = ConfigDict(
        from_attributes=True
    )