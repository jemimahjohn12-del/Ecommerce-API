from datetime import datetime, timezone
from decimal import Decimal

from app.application.interfaces import OrderUnitOfWork
from app.domain.entities import Order, OrderItem, OrderStatus, PaymentStatus
from app.domain.exceptions import CouponNotValid, InsufficientStock, InvalidData, NotFound
from app.domain.repositories import OrderRepository


class Checkout:
    def __init__(self, uow: OrderUnitOfWork):
        self.uow = uow

    def execute(
        self, user_id: int, idempotency_key: str, coupon_code: str | None
    ) -> tuple[Order, bool]:
        """Returns (order, created). created is False when the key was already used."""
        try:
            # Locks this user's cart row: a double click is handled one request at a time
            cart = self.uow.lock_cart(user_id)

            existing = self.uow.find_order_by_key(user_id, idempotency_key)
            if existing:
                self.uow.rollback()  # release the lock
                return existing, False

            if not cart.items:
                raise InvalidData("Your cart is empty")

            # Re-check availability using live data (the brief's "recheck at checkout")
            for item in cart.items:
                if not item.product_is_active:
                    raise InvalidData(f"'{item.product_name}' is no longer available")
                if item.available_stock < item.quantity:
                    raise InsufficientStock(
                        f"Only {item.available_stock} unit(s) of '{item.product_name}' available"
                    )

            subtotal = cart.total  # prices come from the database, never from the client
            discount = Decimal("0.00")
            coupon = None
            if coupon_code:
                coupon = self.uow.get_coupon(coupon_code.strip().upper())
                if not coupon:
                    raise NotFound("Coupon not found")
                coupon.check_usable(subtotal, datetime.now(timezone.utc))
                discount = coupon.calculate_discount(subtotal)

            order = Order(
                id=None,
                user_id=user_id,
                items=[
                    OrderItem(
                        product_id=i.product_id, product_name=i.product_name,
                        unit_price=i.unit_price, quantity=i.quantity,
                    )
                    for i in cart.items
                ],
                subtotal=subtotal,
                discount=discount,
                total=subtotal - discount,
                coupon_code=coupon.code if coupon else None,
            )

            # Atomic stock deduction. Sorted by id so two checkouts never wait on each other in a circle.
            for item in sorted(cart.items, key=lambda i: i.product_id):
                if not self.uow.deduct_stock(item.product_id, item.quantity):
                    raise InsufficientStock(f"Not enough stock for '{item.product_name}'")

            if coupon and not self.uow.use_coupon(coupon.id):
                raise CouponNotValid("This coupon has reached its usage limit")

            saved = self.uow.create_order(order, idempotency_key, coupon.id if coupon else None)
            self.uow.clear_cart(cart.id)
            self.uow.commit()
            return saved, True
        except Exception:
            self.uow.rollback()  # undo stock, coupon, order... everything
            raise


def _cancel_and_restock(uow: OrderUnitOfWork, order: Order) -> None:
    for item in sorted(order.items, key=lambda i: i.product_id):
        uow.add_stock(item.product_id, item.quantity)
    uow.set_order_status(order.id, OrderStatus.CANCELLED)
    order.status = OrderStatus.CANCELLED


class CancelOrder:
    def __init__(self, uow: OrderUnitOfWork):
        self.uow = uow

    def execute(self, user_id: int, order_id: int) -> Order:
        try:
            order = self.uow.lock_order(order_id)  # locked: two cancels can't both restock
            if not order or order.user_id != user_id:
                raise NotFound("Order not found")
            order.ensure_customer_can_cancel()
            _cancel_and_restock(self.uow, order)
            self.uow.commit()
            return order
        except Exception:
            self.uow.rollback()
            raise


class UpdateOrderStatus:
    def __init__(self, uow: OrderUnitOfWork):
        self.uow = uow

    def execute(self, order_id: int, new_status: OrderStatus) -> Order:
        try:
            order = self.uow.lock_order(order_id)
            if not order:
                raise NotFound("Order not found")
            order.ensure_transition(new_status)
            if (
                new_status == OrderStatus.PROCESSING
                and self.uow.get_payment_status(order.id) != PaymentStatus.APPROVED
            ):
                raise InvalidData("Payment must be approved before the order can be processed")

            if new_status == OrderStatus.CANCELLED:
                _cancel_and_restock(self.uow, order)
            else:
                self.uow.set_order_status(order.id, new_status)
                order.status = new_status
            self.uow.commit()
            return order
        except Exception:
            self.uow.rollback()
            raise


class GetOrder:
    def __init__(self, orders: OrderRepository):
        self.orders = orders

    def execute(self, order_id: int, user_id: int, is_admin: bool) -> Order:
        order = self.orders.get_by_id(order_id)
        # Someone else's order looks the same as a missing one
        if not order or (not is_admin and order.user_id != user_id):
            raise NotFound("Order not found")
        return order


class ListMyOrders:
    def __init__(self, orders: OrderRepository):
        self.orders = orders

    def execute(self, user_id: int, page: int, page_size: int):
        return self.orders.list_for_user(user_id, page, page_size)


class ListAllOrders:
    def __init__(self, orders: OrderRepository):
        self.orders = orders

    def execute(self, status: OrderStatus | None, page: int, page_size: int):
        return self.orders.list_all(status, page, page_size)