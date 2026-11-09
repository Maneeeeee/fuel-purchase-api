from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Purchase, User
from app.schemas import PurchaseCreate, PurchaseHistoryItem, PurchaseResponse, TokenRequest, TokenResponse
from app.security import get_current_user, issue_user_token
from app.services import execute_fuel_purchase

router = APIRouter(prefix="/api", tags=["purchases"])


@router.post("/auth/token", response_model=TokenResponse, tags=["auth"])
def generate_user_token(payload: TokenRequest, db: Session = Depends(get_db)):
    """Optional token authentication: issues an API token upon verifying user credentials (username and user_id)."""
    user = (
        db.query(User)
        .filter(User.username == payload.username.strip(), User.id == payload.user_id)
        .first()
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user credentials.",
        )
    token = issue_user_token(user, db)
    return TokenResponse(access_token=token)


@router.post("/purchases", response_model=PurchaseResponse, status_code=status.HTTP_201_CREATED)
def purchase_fuel(
    payload: PurchaseCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return execute_fuel_purchase(db=db, user_id=current_user.id, purchase_data=payload)


@router.get("/purchases", response_model=list[PurchaseHistoryItem])
def get_purchase_history(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    purchases = (
        db.query(Purchase)
        .filter(Purchase.user_id == current_user.id)
        .order_by(Purchase.created_at.desc(), Purchase.id.desc())
        .limit(limit)
        .offset(offset)
        .all()
    )
    return [
        PurchaseHistoryItem(
            id=p.id,
            product=p.product_name,
            litres=f"{p.litres:.2f}",
            total_price=f"{p.total_price:.2f}",
            created_at=p.created_at,
        )
        for p in purchases
    ]
