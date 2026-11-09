import secrets
from typing import Optional

import bcrypt
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Admin, User

BCRYPT_MAX_BYTES = 72


def hash_api_key(raw_key: str) -> str:
    encoded = raw_key.encode("utf-8")
    if len(encoded) > BCRYPT_MAX_BYTES:
        raise ValueError(f"API key must be at most {BCRYPT_MAX_BYTES} bytes.")
    return bcrypt.hashpw(encoded, bcrypt.gensalt()).decode("utf-8")


def verify_api_key(raw_key: str, hashed_key: str) -> bool:
    try:
        return bcrypt.checkpw(raw_key.encode("utf-8"), hashed_key.encode("utf-8"))
    except Exception:
        return False


_UNAUTHORIZED_ADMIN = "Missing or invalid administrator API key."
_UNAUTHORIZED_USER = "Invalid user authentication token."


def get_current_admin(
    x_admin_key: Optional[str] = Header(None, alias="X-Admin-Key"),
    x_admin_username: Optional[str] = Header(None, alias="X-Admin-Username"),
    db: Session = Depends(get_db),
) -> Admin:
    if not x_admin_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=_UNAUTHORIZED_ADMIN)

    # 1. Fast O(1) indexed lookup if X-Admin-Username is provided
    if x_admin_username and x_admin_username.strip():
        admin = db.query(Admin).filter(Admin.username == x_admin_username.strip()).first()
        if admin and verify_api_key(x_admin_key, admin.api_key_hash):
            return admin
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=_UNAUTHORIZED_ADMIN)

    # 2. Spec-compliant fallback for header: X-Admin-Key alone
    admins = db.query(Admin).all()
    for admin in admins:
        if verify_api_key(x_admin_key, admin.api_key_hash):
            return admin

    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=_UNAUTHORIZED_ADMIN)


def issue_user_token(user: User, db: Session) -> str:
    """Generate a secure cryptographic API token for the user, stored in DB."""
    token = secrets.token_hex(32)
    user.api_token = token
    db.commit()
    db.refresh(user)
    return token


def get_current_user(
    authorization: Optional[str] = Header(None, alias="Authorization"),
    x_username: Optional[str] = Header(None, alias="X-Username"),
    db: Session = Depends(get_db),
) -> User:
    # 1. Bearer Token Authentication
    if authorization:
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token.strip():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=_UNAUTHORIZED_USER,
            )
        user = db.query(User).filter(User.api_token == token.strip()).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=_UNAUTHORIZED_USER,
            )
        return user

    # 2. Basic X-Username Authentication
    if not x_username or not x_username.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-Username header.",
        )

    user = db.query(User).filter(User.username == x_username.strip()).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User does not exist.",
        )
    return user
