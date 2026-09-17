

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.database import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.schemas.password import PasswordChangeRequest
from app.schemas.user import UserResponse


router = APIRouter(
    prefix="/users",
    tags=["Users"],
)


@router.get(
    "/me",
    response_model=UserResponse,
)
def get_my_profile(
    current_user: User = Depends(get_current_user),
):
    return current_user


@router.put("/me/password")
def change_my_password(
    data: PasswordChangeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Check the current password
    if not verify_password(
        data.current_password,
        current_user.password_hash,
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )

    # Check minimum password length
    if len(data.new_password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be at least 8 characters",
        )

    # Prevent using the same password
    if data.current_password == data.new_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be different from current password",
        )

    # Replace the password hash
    current_user.password_hash = hash_password(
        data.new_password
    )

    # IMPORTANT: permanently save the change to PostgreSQL
    db.commit()

    return {
        "message": "Password changed successfully",
    }

