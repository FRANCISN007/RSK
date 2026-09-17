
from getpass import getpass

from sqlalchemy import select

from app.core.security import hash_password
from app.database import SessionLocal
from app.models.user import User


def main():
    print("=== RSK Forecasting Platform - Admin Setup ===")

    db = SessionLocal()

    try:
        # Find the existing administrator.
        admin = db.scalar(
            select(User)
            .where(User.is_admin.is_(True))
            .order_by(User.id)
        )

        if admin:
            print()
            print("Existing administrator found.")
            print(f"Current username: {admin.username}")
            print(f"Current email: {admin.email}")
            print()

            full_name = (
                input(
                    f"Admin full name [{admin.full_name}]: "
                ).strip()
                or admin.full_name
            )

            username = (
                input(
                    f"Admin username [{admin.username}]: "
                ).strip()
                or admin.username
            )

            email = (
                input(
                    f"Admin email [{admin.email}]: "
                ).strip()
                or admin.email
            )

            phone_number = input(
                f"Admin phone number "
                f"[{admin.phone_number or 'none'}]: "
            ).strip()

            if not phone_number:
                phone_number = admin.phone_number

            # Check whether another user already owns the
            # requested username or email.
            duplicate_user = db.scalar(
                select(User).where(
                    (
                        (User.username == username)
                        | (User.email == email)
                    )
                    & (User.id != admin.id)
                )
            )

            if duplicate_user:
                print(
                    "Error: Another user already has "
                    "that username or email."
                )
                return

            change_password = input(
                "Change admin password? (y/N): "
            ).strip().lower()

            if change_password == "y":
                password = getpass("New admin password: ")
                confirm_password = getpass(
                    "Confirm new admin password: "
                )

                if password != confirm_password:
                    print("Error: Passwords do not match.")
                    return

                if not password:
                    print("Error: Password cannot be empty.")
                    return

                if len(password) < 8:
                    print(
                        "Error: Password must be at least "
                        "8 characters."
                    )
                    return

                admin.password_hash = hash_password(password)

            # Update administrator details.
            admin.full_name = full_name
            admin.username = username
            admin.email = email
            admin.phone_number = phone_number

            # Make sure the account remains an administrator.
            admin.is_active = True
            admin.is_verified = True
            admin.is_admin = True

            db.commit()
            db.refresh(admin)

            print()
            print("Administrator updated successfully.")
            print(f"Admin ID: {admin.id}")
            print(f"Username: {admin.username}")
            print(f"Email: {admin.email}")

        else:
            # No administrator exists, so create one.
            print()
            print("No administrator found.")
            print("Creating a new administrator.")
            print()

            full_name = input("Admin full name: ").strip()
            username = input("Admin username: ").strip()
            email = input("Admin email: ").strip()
            phone_number = (
                input(
                    "Admin phone number (optional): "
                ).strip()
                or None
            )

            password = getpass("Admin password: ")
            confirm_password = getpass(
                "Confirm admin password: "
            )

            if password != confirm_password:
                print("Error: Passwords do not match.")
                return

            if not password:
                print("Error: Password cannot be empty.")
                return

            if len(password) < 8:
                print(
                    "Error: Password must be at least "
                    "8 characters."
                )
                return

            # Check username/email before creating.
            existing_user = db.scalar(
                select(User).where(
                    (User.username == username)
                    | (User.email == email)
                )
            )

            if existing_user:
                print(
                    "Error: A user with that username "
                    "or email already exists."
                )
                return

            admin = User(
                full_name=full_name,
                username=username,
                email=email,
                phone_number=phone_number,
                password_hash=hash_password(password),
                is_active=True,
                is_verified=True,
                is_admin=True,
            )

            db.add(admin)
            db.commit()
            db.refresh(admin)

            print()
            print("Administrator created successfully.")
            print(f"Admin ID: {admin.id}")
            print(f"Username: {admin.username}")
            print(f"Email: {admin.email}")

    except Exception as exc:
        db.rollback()
        print(f"Error: {exc}")

    finally:
        db.close()


if __name__ == "__main__":
    main()
