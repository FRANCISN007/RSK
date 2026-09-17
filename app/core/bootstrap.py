
from sqlalchemy import select

from app.config import settings
from app.core.security import hash_password
from app.database import SessionLocal
from app.models.user import User


def create_initial_admin():
    db = SessionLocal()

    try:
        existing_admin = db.scalar(
            select(User).where(User.is_admin.is_(True))
        )

        if existing_admin:
            print("Admin account already exists.")
            return

        admin = User(
            full_name=settings.ADMIN_FULL_NAME,
            username=settings.ADMIN_USERNAME,
            email=settings.ADMIN_EMAIL,
            password_hash=hash_password(
                settings.ADMIN_PASSWORD
            ),
            is_active=True,
            is_verified=True,
            is_admin=True,
        )

        db.add(admin)
        db.commit()

        print("Initial admin account created successfully.")

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()
