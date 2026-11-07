from dataclasses import dataclass
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