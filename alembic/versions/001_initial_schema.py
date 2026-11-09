from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "products",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("price_per_litre", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("available_litres", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.CheckConstraint("price_per_litre >= 0", name="check_product_price_non_negative"),
        sa.CheckConstraint("available_litres >= 0", name="check_product_stock_non_negative"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_products_id"), "products", ["id"], unique=False)

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("first_name", sa.String(length=50), nullable=False),
        sa.Column("last_name", sa.String(length=50), nullable=False),
        sa.Column("username", sa.String(length=50), nullable=False),
        sa.Column("birthdate", sa.Date(), nullable=False),
        sa.Column(
            "account_balance",
            sa.Numeric(precision=12, scale=2),
            server_default=sa.text("0.00"),
            nullable=False,
        ),
        sa.CheckConstraint("account_balance >= 0", name="check_user_balance_non_negative"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_id"), "users", ["id"], unique=False)
    op.create_index(op.f("ix_users_username"), "users", ["username"], unique=True)

    op.create_table(
        "admins",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("username", sa.String(length=50), nullable=False),
        sa.Column("api_key_hash", sa.String(length=255), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_admins_id"), "admins", ["id"], unique=False)
    op.create_index(op.f("ix_admins_username"), "admins", ["username"], unique=True)

    op.create_table(
        "purchases",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=True),
        sa.Column("product_name", sa.String(length=100), nullable=False),
        sa.Column("litres", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("total_price", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("litres > 0", name="check_purchase_litres_positive"),
        sa.CheckConstraint("total_price >= 0", name="check_purchase_total_price_non_negative"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_purchases_id"), "purchases", ["id"], unique=False)
    op.create_index(op.f("ix_purchases_user_id"), "purchases", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_purchases_user_id"), table_name="purchases")
    op.drop_index(op.f("ix_purchases_id"), table_name="purchases")
    op.drop_table("purchases")

    op.drop_index(op.f("ix_admins_username"), table_name="admins")
    op.drop_index(op.f("ix_admins_id"), table_name="admins")
    op.drop_table("admins")

    op.drop_index(op.f("ix_users_username"), table_name="users")
    op.drop_index(op.f("ix_users_id"), table_name="users")
    op.drop_table("users")

    op.drop_index(op.f("ix_products_id"), table_name="products")
    op.drop_table("products")
