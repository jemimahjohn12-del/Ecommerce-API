from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum

from app.domain.exceptions import InvalidData


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