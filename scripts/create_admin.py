import argparse
import secrets
import sys

from app.database import SessionLocal
from app.models import Admin
from app.security import hash_api_key


def main():
    parser = argparse.ArgumentParser(description="Create or update an administrator account.")
    parser.add_argument("--username", type=str, default="admin",
                        help="Administrator username (default: 'admin')")
    parser.add_argument("--api-key", type=str, default=None,
                        help="Raw API key, max 72 bytes (if omitted, a secure random key is generated)")
    args = parser.parse_args()

    username = args.username.strip()
    if not username:
        print("Error: username must not be empty.", file=sys.stderr)
        sys.exit(1)

    raw_key = args.api_key.strip() if args.api_key else secrets.token_urlsafe(24)
    try:
        hashed_key = hash_api_key(raw_key)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    db = SessionLocal()
    try:
        admin = db.query(Admin).filter(Admin.username == username).first()
        if admin:
            admin.api_key_hash = hashed_key
            print(f"Updated existing admin user: {username}")
        else:
            db.add(Admin(username=username, api_key_hash=hashed_key))
            print(f"Created new admin user: {username}")

        db.commit()

        print("-" * 50)
        print("Admin Credentials:")
        print(f"Username:    {username}")
        print(f"X-Admin-Key: {raw_key}")
        print("-" * 50)
        print("Save this API key. It is required in the X-Admin-Key header for admin endpoints.")
    except Exception as e:
        db.rollback()
        print(f"Error creating admin: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
