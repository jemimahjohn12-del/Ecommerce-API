from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean, CheckConstraint, DateTime, ForeignKey, Integer, Numeric, String, Text,
    UniqueConstraint, func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database import Base
class UserModel(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(255))
    hashed_password: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default="CUSTOMER")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CategoryModel(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)


class ProductModel(Base):
    __tablename__ = "products"
    # The database itself refuses bad data, even if the app has a bug
    __table_args__ = (
        CheckConstraint("price > 0", name="ck_products_price_positive"),
        CheckConstraint("stock >= 0", name="ck_products_stock_non_negative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    stock: Mapped[int] = mapped_column(Integer, default=0)
    sku: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"), index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    

class CartModel(Base):
    __tablename__ = "carts"

    id: Mapped[int] = mapped_column(primary_key=True)
    # unique=True => one cart per user, enforced by the database
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CartItemModel(Base):
    __tablename__ = "cart_items"
    __table_args__ = (
        UniqueConstraint("cart_id", "product_id", name="uq_cart_items_cart_product"),
        CheckConstraint("quantity > 0", name="ck_cart_items_quantity_positive"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    cart_id: Mapped[int] = mapped_column(ForeignKey("carts.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    quantity: Mapped[int] = mapped_column(Integer)
    

class CouponModel(Base):
    __tablename__ = "coupons"
    __table_args__ = (
        CheckConstraint("discount_value > 0", name="ck_coupons_value_positive"),
        CheckConstraint(
            "discount_type <> 'PERCENTAGE' OR discount_value <= 100",
            name="ck_coupons_percentage_max_100",
        ),
        CheckConstraint("max_uses >= 1", name="ck_coupons_max_uses_positive"),
        CheckConstraint("min_order_amount >= 0", name="ck_coupons_min_order_non_negative"),
        CheckConstraint("times_used >= 0", name="ck_coupons_times_used_non_negative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    discount_type: Mapped[str] = mapped_column(String(20))
    discount_value: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    max_uses: Mapped[int] = mapped_column(Integer)
    min_order_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    times_used: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    

class OrderModel(Base):
    __tablename__ = "orders"
    __table_args__ = (
        CheckConstraint("total >= 0", name="ck_orders_total_non_negative"),
        CheckConstraint("discount >= 0", name="ck_orders_discount_non_negative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="PENDING", index=True)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    discount: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"))
    total: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    coupon_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class OrderItemModel(Base):
    __tablename__ = "order_items"
    __table_args__ = (CheckConstraint("quantity > 0", name="ck_order_items_quantity_positive"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    product_name: Mapped[str] = mapped_column(String(255))  # snapshot
    unit_price: Mapped[Decimal] = mapped_column(Numeric(10, 2))  # snapshot
    quantity: Mapped[int] = mapped_column(Integer)


class CouponUsageModel(Base):
    __tablename__ = "coupon_usages"
    __table_args__ = (UniqueConstraint("order_id", name="uq_coupon_usages_order"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    coupon_id: Mapped[int] = mapped_column(ForeignKey("coupons.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class IdempotencyKeyModel(Base):
    __tablename__ = "idempotency_keys"
    # The database itself refuses a second order for the same user and key
    __table_args__ = (UniqueConstraint("user_id", "key", name="uq_idempotency_user_key"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    key: Mapped[str] = mapped_column(String(100))
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())