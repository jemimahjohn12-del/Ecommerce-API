from dataclasses import dataclass, field
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from enum import Enum

from app.domain.exceptions import CouponNotValid, InvalidData


class Role(str, Enum):
    CUSTOMER = "CUSTOMER"
    ADMIN = "ADMIN"


@dataclass
class User:
    id: int | None
    email: str
    full_name: str
    hashed_password: str
    role: Role = Role.CUSTOMER
    is_active: bool = True


@dataclass
class Category:
    id: int | None
    name: str
    description: str | None = None


@dataclass
class Product:
    id: int | None
    name: str
    description: str | None
    price: Decimal
    stock: int
    sku: str
    category_id: int
    is_active: bool = True
    created_at: datetime | None = None

    def __post_init__(self):
        self.validate()

    def validate(self) -> None:
        """Business rules that every product must obey."""
        if self.price <= 0:
            raise InvalidData("Price must be greater than 0")
        if self.stock < 0:
            raise InvalidData("Stock cannot be negative")
        

@dataclass
class CartItem:
    product_id: int
    product_name: str
    unit_price: Decimal
    quantity: int
    available_stock: int
    product_is_active: bool

    @property
    def line_total(self) -> Decimal:
        return self.unit_price * self.quantity

    @property
    def is_available(self) -> bool:
        """False if the product was deactivated or stock dropped below the quantity."""
        return self.product_is_active and self.available_stock >= self.quantity


@dataclass
class Cart:
    id: int | None
    user_id: int
    items: list[CartItem] = field(default_factory=list)

    @property
    def total(self) -> Decimal:
        return sum((item.line_total for item in self.items), Decimal("0.00"))

    @property
    def item_count(self) -> int:
        return sum(item.quantity for item in self.items)
    

class DiscountType(str, Enum):
    PERCENTAGE = "PERCENTAGE"
    FIXED = "FIXED"


@dataclass
class Coupon:
    id: int | None
    code: str
    discount_type: DiscountType
    discount_value: Decimal
    expires_at: datetime
    max_uses: int
    min_order_amount: Decimal = Decimal("0.00")
    is_active: bool = True
    times_used: int = 0
    created_at: datetime | None = None

    def __post_init__(self):
        self.validate()

    def validate(self) -> None:
        if self.discount_value <= 0:
            raise InvalidData("Discount value must be greater than 0")
        if self.discount_type == DiscountType.PERCENTAGE and self.discount_value > 100:
            raise InvalidData("Percentage discount must be between 0 and 100")
        if self.max_uses < 1:
            raise InvalidData("Maximum usage limit must be at least 1")
        if self.min_order_amount < 0:
            raise InvalidData("Minimum order amount cannot be negative")

    def check_usable(self, order_total: Decimal, now: datetime) -> None:
        if not self.is_active:
            raise CouponNotValid("This coupon is inactive")
        if now >= self.expires_at:
            raise CouponNotValid("This coupon has expired")
        if self.times_used >= self.max_uses:
            raise CouponNotValid("This coupon has reached its usage limit")
        if order_total < self.min_order_amount:
            raise CouponNotValid(f"Minimum order amount for this coupon is {self.min_order_amount}")

    def calculate_discount(self, order_total: Decimal) -> Decimal:
        if self.discount_type == DiscountType.PERCENTAGE:
            discount = (order_total * self.discount_value / 100).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
        else:
            discount = self.discount_value
        # The final total must never be negative
        return min(discount, order_total)