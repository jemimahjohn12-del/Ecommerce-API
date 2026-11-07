from datetime import datetime, timezone
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.domain.entities import DiscountType, OrderStatus

# ---------- Auth ----------
class RegisterRequest(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=8, max_length=72)
    # No "role" field here on purpose


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    full_name: str
    role: str
    # No password field here on purpose


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ---------- Categories ----------
class CategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)


class CategoryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)


class CategoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None


# ---------- Products ----------
class ProductCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    price: Decimal = Field(gt=0, max_digits=10, decimal_places=2)
    stock: int = Field(ge=0)
    sku: str = Field(min_length=1, max_length=50)
    category_id: int = Field(ge=1)


class ProductUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    price: Decimal | None = Field(default=None, gt=0, max_digits=10, decimal_places=2)
    stock: int | None = Field(default=None, ge=0)
    sku: str | None = Field(default=None, min_length=1, max_length=50)
    category_id: int | None = Field(default=None, ge=1)
    is_active: bool | None = None


class StockUpdate(BaseModel):
    stock: int = Field(ge=0)


class ProductResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None
    price: Decimal
    stock: int
    sku: str
    category_id: int
    is_active: bool
    created_at: datetime


class PaginatedProducts(BaseModel):
    items: list[ProductResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
    

# ---------- Cart ----------
class AddToCartRequest(BaseModel):
    product_id: int = Field(ge=1)
    quantity: int = Field(default=1, ge=1, le=1000)


class UpdateCartItemRequest(BaseModel):
    quantity: int = Field(ge=1, le=1000)


class CartItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    product_id: int
    product_name: str
    unit_price: Decimal
    quantity: int
    line_total: Decimal
    is_available: bool


class CartResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    items: list[CartItemResponse]
    item_count: int
    total: Decimal
    

# ---------- Coupons ----------
def _as_utc(value: datetime | None) -> datetime | None:
    # A date sent without a time zone is treated as UTC
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


class CouponCreate(BaseModel):
    code: str = Field(min_length=3, max_length=50)
    discount_type: DiscountType
    discount_value: Decimal = Field(gt=0, max_digits=10, decimal_places=2)
    expires_at: datetime
    max_uses: int = Field(ge=1)
    min_order_amount: Decimal = Field(default=Decimal("0.00"), ge=0, max_digits=10, decimal_places=2)
    is_active: bool = True

    _utc = field_validator("expires_at")(_as_utc)


class CouponUpdate(BaseModel):
    discount_type: DiscountType | None = None
    discount_value: Decimal | None = Field(default=None, gt=0, max_digits=10, decimal_places=2)
    expires_at: datetime | None = None
    max_uses: int | None = Field(default=None, ge=1)
    min_order_amount: Decimal | None = Field(default=None, ge=0, max_digits=10, decimal_places=2)
    is_active: bool | None = None

    _utc = field_validator("expires_at")(_as_utc)


class CouponResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    discount_type: DiscountType
    discount_value: Decimal
    expires_at: datetime
    max_uses: int
    times_used: int
    min_order_amount: Decimal
    is_active: bool
    created_at: datetime


class ApplyCouponRequest(BaseModel):
    code: str = Field(min_length=1, max_length=50)


class AppliedCouponResponse(BaseModel):
    code: str
    subtotal: Decimal
    discount: Decimal
    final_total: Decimal
    

# ---------- Orders ----------
class CheckoutRequest(BaseModel):
    coupon_code: str | None = Field(default=None, min_length=1, max_length=50)


class OrderItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    product_id: int
    product_name: str
    unit_price: Decimal
    quantity: int
    line_total: Decimal


class OrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    status: OrderStatus
    items: list[OrderItemResponse]
    subtotal: Decimal
    discount: Decimal
    total: Decimal
    coupon_code: str | None
    created_at: datetime


class PaginatedOrders(BaseModel):
    items: list[OrderResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class UpdateOrderStatusRequest(BaseModel):
    status: OrderStatus