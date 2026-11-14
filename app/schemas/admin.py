from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr


class AdminUserResponse(BaseModel):
    id: int
    full_name: str
    username: str
    email: str
    phone_number: str | None
    is_active: bool
    is_verified: bool
    is_admin: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AdminUserStatusUpdate(BaseModel):
    is_active: bool | None = None
    is_verified: bool | None = None


from pydantic import BaseModel, Field


class MembershipDeactivateRequest(BaseModel):
    reason: str = Field(
        ...,
        min_length=3,
        max_length=500,
    )


