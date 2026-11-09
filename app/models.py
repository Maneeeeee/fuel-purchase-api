from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    price_per_litre: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    available_litres: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    __table_args__ = (
        CheckConstraint("price_per_litre >= 0", name="check_product_price_non_negative"),
        CheckConstraint("available_litres >= 0", name="check_product_stock_non_negative"),
    )


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    first_name: Mapped[str] = mapped_column(String(50), nullable=False)
    last_name: Mapped[str] = mapped_column(String(50), nullable=False)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    birthdate: Mapped[date] = mapped_column(Date, nullable=False)
    account_balance: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0.00"), nullable=False
    )
    api_token: Mapped[Optional[str]] = mapped_column(String(64), unique=True, index=True, nullable=True)

    purchases: Mapped[list["Purchase"]] = relationship("Purchase", back_populates="user")

    __table_args__ = (
        CheckConstraint("account_balance >= 0", name="check_user_balance_non_negative"),
    )


class Admin(Base):
    __tablename__ = "admins"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    api_key_hash: Mapped[str] = mapped_column(String(255), nullable=False)


class Purchase(Base):
    __tablename__ = "purchases"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    product_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("products.id", ondelete="SET NULL"), nullable=True
    )
    product_name: Mapped[str] = mapped_column(String(100), nullable=False)
    litres: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    total_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped["User"] = relationship("User", back_populates="purchases")
    product: Mapped[Optional["Product"]] = relationship("Product")

    __table_args__ = (
        CheckConstraint("litres > 0", name="check_purchase_litres_positive"),
        CheckConstraint("total_price >= 0", name="check_purchase_total_price_non_negative"),
    )
