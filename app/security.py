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


_UNAUTHORIZED = "Missing or invalid administrator API key."


def get_current_admin(
    x_admin_key: Optional[str] = Header(None, alias="X-Admin-Key"),
    db: Session = Depends(get_db),
) -> Admin:
    if not x_admin_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=_UNAUTHORIZED)

    admins = db.query(Admin).all()
    for admin in admins:
        if verify_api_key(x_admin_key, admin.api_key_hash):
            return admin

    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=_UNAUTHORIZED)



def get_current_user(
    x_username: Optional[str] = Header(None, alias="X-Username"),
    db: Session = Depends(get_db),
) -> User:
    if not x_username or not x_username.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing X-Username header.",
        )

    user = db.query(User).filter(User.username == x_username.strip()).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User does not exist.",
        )
    return user
