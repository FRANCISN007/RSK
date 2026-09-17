from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.user import User
from app.models.membership import MembershipPlan


class MembershipOrder(Base):
    __tablename__ = "membership_orders"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    plan_id: Mapped[int] = mapped_column(
        ForeignKey("membership_plans.id"),
        nullable=False,
        index=True,
    )

    # Price is copied from the plan when the order is created.
    # This protects the order if the plan price changes later.
    amount: Mapped[float] = mapped_column(
        Numeric(12, 2),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    paid_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    user: Mapped["User"] = relationship()

    plan: Mapped["MembershipPlan"] = relationship()