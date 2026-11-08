from dataclasses import dataclass, field
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from enum import Enum

from app.domain.exceptions import CouponNotValid, InvalidData, InvalidStatusTransition

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
    

class OrderStatus(str, Enum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    PROCESSING = "PROCESSING"
    SHIPPED = "SHIPPED"
    DELIVERED = "DELIVERED"
    CANCELLED = "CANCELLED"


# Which status may follow which. A delivered order can never be cancelled.
ALLOWED_TRANSITIONS: dict[OrderStatus, set[OrderStatus]] = {
    OrderStatus.PENDING: {OrderStatus.CONFIRMED, OrderStatus.CANCELLED},
    OrderStatus.CONFIRMED: {OrderStatus.PROCESSING, OrderStatus.CANCELLED},
    OrderStatus.PROCESSING: {OrderStatus.SHIPPED, OrderStatus.CANCELLED},
    OrderStatus.SHIPPED: {OrderStatus.DELIVERED},
    OrderStatus.DELIVERED: set(),
    OrderStatus.CANCELLED: set(),
}

# Customers may only cancel before processing starts
CUSTOMER_CANCELLABLE = {OrderStatus.PENDING, OrderStatus.CONFIRMED}


@dataclass
class OrderItem:
    product_id: int
    product_name: str  # snapshot at purchase time
    unit_price: Decimal  # snapshot at purchase time
    quantity: int

    @property
    def line_total(self) -> Decimal:
        return self.unit_price * self.quantity


@dataclass
class Order:
    id: int | None
    user_id: int
    items: list[OrderItem]
    subtotal: Decimal
    discount: Decimal
    total: Decimal
    status: OrderStatus = OrderStatus.PENDING
    coupon_code: str | None = None
    created_at: datetime | None = None

    def __post_init__(self):
        if self.total < 0:
            raise InvalidData("Order total cannot be negative")

    def ensure_transition(self, new_status: OrderStatus) -> None:
        if new_status not in ALLOWED_TRANSITIONS[self.status]:
            raise InvalidStatusTransition(
                f"Cannot change order status from {self.status.value} to {new_status.value}"
            )

    def ensure_customer_can_cancel(self) -> None:
        if self.status not in CUSTOMER_CANCELLABLE:
            raise InvalidStatusTransition(f"An order that is {self.status.value} cannot be cancelled")
        

class PaymentStatus(str, Enum):
    NOT_SUBMITTED = "NOT_SUBMITTED"
    UNDER_REVIEW = "UNDER_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


@dataclass
class Payment:
    id: int | None
    order_id: int
    user_id: int
    amount: Decimal
    content_type: str
    status: PaymentStatus = PaymentStatus.UNDER_REVIEW
    rejection_reason: str | None = None
    reviewed_by: int | None = None
    reviewed_at: datetime | None = None
    submitted_at: datetime | None = None

    def ensure_reviewable(self) -> None:
        if self.status != PaymentStatus.UNDER_REVIEW:
            raise InvalidStatusTransition(
                "Only a payment that is under review can be approved or rejected"
            )