from decimal import Decimal, ROUND_HALF_UP

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models import Product, Purchase, User
from app.schemas import PurchaseCreate, PurchaseResponse


def execute_fuel_purchase(
    db: Session,
    user_id: int,
    purchase_data: PurchaseCreate,
) -> PurchaseResponse:
    if purchase_data.litres <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Litres must be greater than zero.",
        )

    try:
        user = (
            db.query(User)
            .filter(User.id == user_id)
            .populate_existing()
            .with_for_update()
            .first()
        )
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User does not exist.",
            )

        product = (
            db.query(Product)
            .filter(Product.id == purchase_data.product_id)
            .populate_existing()
            .with_for_update()
            .first()
        )
        if not product:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Product does not exist.",
            )

        if product.available_litres < purchase_data.litres:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Not enough fuel available.",
            )

        total_price = (product.price_per_litre * purchase_data.litres).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

        if user.account_balance < total_price:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Insufficient balance.",
            )

        user.account_balance -= total_price
        product.available_litres -= purchase_data.litres

        purchase = Purchase(
            user_id=user.id,
            product_id=product.id,
            product_name=product.name,
            litres=purchase_data.litres,
            total_price=total_price,
        )
        db.add(purchase)
        db.commit()
        db.refresh(purchase)

        return PurchaseResponse(
            id=purchase.id,
            product=purchase.product_name,
            litres=f"{purchase.litres:.2f}",
            total_price=f"{purchase.total_price:.2f}",
            remaining_balance=f"{user.account_balance:.2f}",
            remaining_stock_litres=f"{product.available_litres:.2f}",
        )
    except Exception:
        db.rollback()
        raise
