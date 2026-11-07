from abc import ABC, abstractmethod
from app.domain.entities import Cart, Coupon, Order, OrderStatus

class PasswordHasher(ABC):
    @abstractmethod
    def hash(self, password: str) -> str: ...

    @abstractmethod
    def verify(self, password: str, hashed: str) -> bool: ...


class TokenService(ABC):
    @abstractmethod
    def create_access_token(self, user_id: int, role: str) -> str: ...

    @abstractmethod
    def decode_token(self, token: str) -> int:
        """Return the user id or raise InvalidCredentials."""
        

class OrderUnitOfWork(ABC):
    """Operations that must all succeed or all be undone (one database transaction)."""

    @abstractmethod
    def lock_cart(self, user_id: int) -> Cart: ...

    @abstractmethod
    def find_order_by_key(self, user_id: int, key: str) -> Order | None: ...

    @abstractmethod
    def get_coupon(self, code: str) -> Coupon | None: ...

    @abstractmethod
    def deduct_stock(self, product_id: int, quantity: int) -> bool:
        """Atomically remove stock. Returns False if there is not enough."""

    @abstractmethod
    def add_stock(self, product_id: int, quantity: int) -> None: ...

    @abstractmethod
    def use_coupon(self, coupon_id: int) -> bool:
        """Atomically count one use. Returns False if the usage limit was reached."""

    @abstractmethod
    def create_order(self, order: Order, idempotency_key: str, coupon_id: int | None) -> Order: ...

    @abstractmethod
    def clear_cart(self, cart_id: int) -> None: ...

    @abstractmethod
    def lock_order(self, order_id: int) -> Order | None: ...

    @abstractmethod
    def set_order_status(self, order_id: int, status: OrderStatus) -> None: ...

    @abstractmethod
    def commit(self) -> None: ...

    @abstractmethod
    def rollback(self) -> None: ...