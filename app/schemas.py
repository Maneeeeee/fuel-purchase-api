from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Annotated, Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_serializer,
    field_validator,
)

# Money / quantity types: limits mirror the Numeric(precision, 2) columns so that
# what is validated is exactly what is stored (no hidden rounding, no overflow).
Price = Annotated[Decimal, Field(ge=0, max_digits=10, decimal_places=2)]
Litres = Annotated[Decimal, Field(ge=0, max_digits=10, decimal_places=2)]
Balance = Annotated[Decimal, Field(ge=0, max_digits=12, decimal_places=2)]

# Primary keys are 32-bit integers; larger values would error in PostgreSQL.
IntId = Annotated[int, Field(ge=1, le=2_147_483_647)]

Name50 = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)]
ProductName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]


def _check_birthdate(v: Optional[date]) -> Optional[date]:
    if v is not None and v > date.today():
        raise ValueError("Birthdate cannot be in the future.")
    return v


class _RejectNullUpdate(BaseModel):
    """PATCH models: a field may be omitted, but never explicitly set to null."""

    @field_validator("*", mode="before")
    @classmethod
    def _reject_null(cls, v):
        if v is None:
            raise ValueError("Field may not be null.")
        return v


class ProductCreate(BaseModel):
    name: ProductName
    price_per_litre: Price
    available_litres: Litres


class ProductUpdate(_RejectNullUpdate):
    name: Optional[ProductName] = None
    price_per_litre: Optional[Price] = None
    available_litres: Optional[Litres] = None


class ProductResponse(BaseModel):
    id: int
    name: str
    price_per_litre: Decimal
    available_litres: Decimal
    model_config = ConfigDict(from_attributes=True)

    @field_serializer("price_per_litre", "available_litres", when_used="json")
    def format_decimal(self, v: Decimal) -> str:
        return f"{v:.2f}"


class UserCreate(BaseModel):
    first_name: Name50
    last_name: Name50
    username: Name50
    birthdate: date
    account_balance: Balance = Decimal("0.00")

    _birthdate_not_future = field_validator("birthdate")(_check_birthdate)


class UserUpdate(_RejectNullUpdate):
    first_name: Optional[Name50] = None
    last_name: Optional[Name50] = None
    username: Optional[Name50] = None
    birthdate: Optional[date] = None
    account_balance: Optional[Balance] = None

    _birthdate_not_future = field_validator("birthdate")(_check_birthdate)


class UserResponse(BaseModel):
    id: int
    first_name: str
    last_name: str
    username: str
    birthdate: date
    account_balance: Decimal
    api_token: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)

    @field_serializer("account_balance", when_used="json")
    def format_balance(self, v: Decimal) -> str:
        return f"{v:.2f}"


class PurchaseCreate(BaseModel):
    product_id: IntId
    # Positivity is enforced in the service layer so zero/negative litres
    # produce a 400 Bad Request (a business-rule error), not a 422.
    litres: Annotated[Decimal, Field(max_digits=10, decimal_places=2)]


class PurchaseResponse(BaseModel):
    id: int
    product: str
    litres: str
    total_price: str
    remaining_balance: str
    remaining_stock_litres: str


class PurchaseHistoryItem(BaseModel):
    id: int
    product: str
    litres: str
    total_price: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

    @field_serializer("created_at", when_used="json")
    def format_created_at(self, v: datetime) -> str:
        # Naive values (SQLite) are UTC; aware values are converted to UTC.
        if v.tzinfo is None:
            v = v.replace(tzinfo=timezone.utc)
        return v.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


class ErrorResponse(BaseModel):
    error: str


class TokenRequest(BaseModel):
    username: Name50
    user_id: IntId


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
