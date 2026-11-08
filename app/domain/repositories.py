from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal

from app.domain.entities import (
    Cart, Category, Coupon, Order, OrderStatus, Payment, PaymentStatus, Product, User,
)


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
    

class CartRepository(ABC):
    @abstractmethod
    def get_cart(self, user_id: int) -> Cart:
        """Return the user's cart, creating an empty one if needed."""

    @abstractmethod
    def get_item_quantity(self, user_id: int, product_id: int) -> int | None: ...

    @abstractmethod
    def set_item_quantity(self, user_id: int, product_id: int, quantity: int) -> None:
        """Insert the item, or update its quantity if it is already in the cart."""

    @abstractmethod
    def remove_item(self, user_id: int, product_id: int) -> bool: ...

    @abstractmethod
    def clear(self, user_id: int) -> None: ...
    

class CouponRepository(ABC):
    @abstractmethod
    def get_by_id(self, coupon_id: int) -> Coupon | None: ...

    @abstractmethod
    def get_by_code(self, code: str) -> Coupon | None: ...

    @abstractmethod
    def list_all(self) -> list[Coupon]: ...

    @abstractmethod
    def add(self, coupon: Coupon) -> Coupon: ...

    @abstractmethod
    def update(self, coupon: Coupon) -> Coupon: ...
    

class OrderRepository(ABC):
    """Read side for orders. Writing happens through OrderUnitOfWork."""

    @abstractmethod
    def get_by_id(self, order_id: int) -> Order | None: ...

    @abstractmethod
    def list_for_user(self, user_id: int, page: int, page_size: int) -> tuple[list[Order], int]: ...

    @abstractmethod
    def list_all(
        self, status: OrderStatus | None, page: int, page_size: int
    ) -> tuple[list[Order], int]: ...
    

class PaymentRepository(ABC):
    @abstractmethod
    def get_by_id(self, payment_id: int) -> Payment | None: ...

    @abstractmethod
    def get_latest_for_order(self, order_id: int) -> Payment | None: ...

    @abstractmethod
    def list_for_order(self, order_id: int) -> list[Payment]:
        """All submissions for an order, newest first."""

    @abstractmethod
    def list_all(
        self, status: PaymentStatus | None, page: int, page_size: int
    ) -> tuple[list[Payment], int]: ...

    @abstractmethod
    def add(self, payment: Payment, receipt: bytes) -> Payment: ...

    @abstractmethod
    def get_receipt(self, payment_id: int) -> bytes | None: ...