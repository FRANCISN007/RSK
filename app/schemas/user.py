from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr


class UserCreate(BaseModel):
    full_name: str
    username: str
    email: EmailStr
    phone_number: str | None = None
    password: str


class UserResponse(BaseModel):
    id: int
    full_name: str
    username: str
    email: EmailStr
    phone_number: str | None
    is_active: bool
    is_verified: bool
    is_admin: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)