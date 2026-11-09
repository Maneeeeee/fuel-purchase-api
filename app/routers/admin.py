from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Admin, Product, User
from app.schemas import (
    ProductCreate,
    ProductResponse,
    ProductUpdate,
    UserCreate,
    UserResponse,
    UserUpdate,
)
from app.security import get_current_admin

router = APIRouter(prefix="/api/admin", tags=["admin"])

PathId = Annotated[int, Path(ge=1, le=2_147_483_647)]

_USERNAME_TAKEN = "Username already exists."


def _commit_unique_username(db: Session) -> None:
    """Commit, turning a lost username race (unique violation) into a 400."""
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=_USERNAME_TAKEN) from None


# Every route is registered with and without a trailing slash so clients never
# hit a 307 redirect (which many HTTP clients do not follow for POST/PATCH).


@router.post("/products/", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
@router.post(
    "/products",
    response_model=ProductResponse,
    status_code=status.HTTP_201_CREATED,
    include_in_schema=False,
)
def create_product(
    payload: ProductCreate,
    db: Session = Depends(get_db),
    _: Admin = Depends(get_current_admin),
):
    product = Product(
        name=payload.name,
        price_per_litre=payload.price_per_litre,
        available_litres=payload.available_litres,
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


@router.patch("/products/{product_id}/", response_model=ProductResponse)
@router.patch("/products/{product_id}", response_model=ProductResponse, include_in_schema=False)
def update_product(
    product_id: PathId,
    payload: ProductUpdate,
    db: Session = Depends(get_db),
    _: Admin = Depends(get_current_admin),
):
    # Row lock serialises this edit with in-flight purchases.
    product = db.query(Product).filter(Product.id == product_id).populate_existing().with_for_update().first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product does not exist.",
        )

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(product, field, value)

    db.commit()
    db.refresh(product)
    return product


@router.post("/users/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
@router.post(
    "/users",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    include_in_schema=False,
)
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    _: Admin = Depends(get_current_admin),
):
    if db.query(User).filter(User.username == payload.username).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=_USERNAME_TAKEN)

    user = User(
        first_name=payload.first_name,
        last_name=payload.last_name,
        username=payload.username,
        birthdate=payload.birthdate,
        account_balance=payload.account_balance,
    )
    db.add(user)
    _commit_unique_username(db)
    db.refresh(user)
    return user


@router.patch("/users/{user_id}/", response_model=UserResponse)
@router.patch("/users/{user_id}", response_model=UserResponse, include_in_schema=False)
def update_user(
    user_id: PathId,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    _: Admin = Depends(get_current_admin),
):
    user = db.query(User).filter(User.id == user_id).populate_existing().with_for_update().first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User does not exist.",
        )

    update_data = payload.model_dump(exclude_unset=True)
    new_username = update_data.get("username")
    if new_username is not None and new_username != user.username:
        if db.query(User).filter(User.username == new_username).first():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=_USERNAME_TAKEN)

    for field, value in update_data.items():
        setattr(user, field, value)

    _commit_unique_username(db)
    db.refresh(user)
    return user
