from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
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
_PRODUCT_NAME_TAKEN = "Product name already exists."


def _commit_or_handle_integrity(db: Session, duplicate_msg: str) -> None:
    """Commit transaction, converting unique constraint violations into 400."""
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=duplicate_msg) from None


@router.get("/products", response_model=list[ProductResponse])
def list_products(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    _: Admin = Depends(get_current_admin),
):
    """Retrieve all fuel products (admin convenience endpoint)."""
    return db.query(Product).order_by(Product.id.asc()).limit(limit).offset(offset).all()


@router.post("/products", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
def create_product(
    payload: ProductCreate,
    db: Session = Depends(get_db),
    _: Admin = Depends(get_current_admin),
):
    if db.query(Product).filter(Product.name == payload.name).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=_PRODUCT_NAME_TAKEN)

    product = Product(
        name=payload.name,
        price_per_litre=payload.price_per_litre,
        available_litres=payload.available_litres,
    )
    db.add(product)
    _commit_or_handle_integrity(db, _PRODUCT_NAME_TAKEN)
    db.refresh(product)
    return product


@router.patch("/products/{product_id}", response_model=ProductResponse)
def update_product(
    product_id: PathId,
    payload: ProductUpdate,
    db: Session = Depends(get_db),
    _: Admin = Depends(get_current_admin),
):
    product = db.query(Product).filter(Product.id == product_id).populate_existing().with_for_update().first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product does not exist.",
        )

    update_data = payload.model_dump(exclude_unset=True)
    new_name = update_data.get("name")
    if new_name is not None and new_name != product.name:
        if db.query(Product).filter(Product.name == new_name).first():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=_PRODUCT_NAME_TAKEN)

    for field, value in update_data.items():
        setattr(product, field, value)

    _commit_or_handle_integrity(db, _PRODUCT_NAME_TAKEN)
    db.refresh(product)
    return product


@router.get("/users", response_model=list[UserResponse])
def list_users(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    _: Admin = Depends(get_current_admin),
):
    """Retrieve all users (admin convenience endpoint)."""
    return db.query(User).order_by(User.id.asc()).limit(limit).offset(offset).all()


@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
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
    _commit_or_handle_integrity(db, _USERNAME_TAKEN)
    db.refresh(user)
    return user


@router.patch("/users/{user_id}", response_model=UserResponse)
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

    _commit_or_handle_integrity(db, _USERNAME_TAKEN)
    db.refresh(user)
    return user
