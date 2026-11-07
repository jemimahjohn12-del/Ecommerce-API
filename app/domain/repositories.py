from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal

from app.domain.entities import Category, Product, User


class UserRepository(ABC):
    @abstractmethod
    def get_by_email(self, email: str) -> User | None: ...

    @abstractmethod
    def get_by_id(self, user_id: int) -> User | None: ...

    @abstractmethod
    def add(self, user: User) -> User: ...


@dataclass
class ProductFilter:
    search: str | None = None
    category_id: int | None = None
    min_price: Decimal | None = None
    max_price: Decimal | None = None
    sort_by: str = "created_at"  # "price" or "created_at"
    sort_order: str = "desc"  # "asc" or "desc"
    include_inactive: bool = False
    page: int = 1
    page_size: int = 10


class CategoryRepository(ABC):
    @abstractmethod
    def get_by_id(self, category_id: int) -> Category | None: ...

    @abstractmethod
    def get_by_name(self, name: str) -> Category | None: ...

    @abstractmethod
    def list_all(self) -> list[Category]: ...

    @abstractmethod
    def add(self, category: Category) -> Category: ...

    @abstractmethod
    def update(self, category: Category) -> Category: ...

    @abstractmethod
    def delete(self, category_id: int) -> None: ...

    @abstractmethod
    def has_products(self, category_id: int) -> bool: ...


class ProductRepository(ABC):
    @abstractmethod
    def get_by_id(self, product_id: int) -> Product | None: ...

    @abstractmethod
    def get_by_sku(self, sku: str) -> Product | None: ...

    @abstractmethod
    def search(self, filters: ProductFilter) -> tuple[list[Product], int]:
        """Return (products on this page, total matching products)."""

    @abstractmethod
    def add(self, product: Product) -> Product: ...

    @abstractmethod
    def update(self, product: Product) -> Product: ...