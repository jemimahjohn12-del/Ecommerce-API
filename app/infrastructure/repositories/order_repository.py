from collections import defaultdict

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from app.application.interfaces import OrderUnitOfWork
from app.domain.entities import Cart, Coupon, Order, OrderItem, OrderStatus, Payment, PaymentStatus
from app.domain.repositories import OrderRepository
from app.infrastructure.models import (
    CartItemModel, CartModel, CouponModel, CouponUsageModel, IdempotencyKeyModel,
    OrderItemModel, OrderModel, ProductModel,
)
from app.infrastructure.repositories.cart_repository import SqlAlchemyCartRepository
from app.infrastructure.repositories.coupon_repository import SqlAlchemyCouponRepository
from app.infrastructure.repositories.payment_repository import SqlAlchemyPaymentRepository


def _to_orders(db: Session, models: list[OrderModel]) -> list[Order]:
    """Turn order rows into Order entities (loads all their items in one query)."""
    if not models:
        return []
    rows = db.scalars(
        select(OrderItemModel)
        .where(OrderItemModel.order_id.in_([m.id for m in models]))
        .order_by(OrderItemModel.id)
    ).all()
    items_by_order = defaultdict(list)
    for r in rows:
        items_by_order[r.order_id].append(
            OrderItem(
                product_id=r.product_id, product_name=r.product_name,
                unit_price=r.unit_price, quantity=r.quantity,
            )
        )
    return [
        Order(
            id=m.id, user_id=m.user_id, items=items_by_order[m.id], subtotal=m.subtotal,
            discount=m.discount, total=m.total, status=OrderStatus(m.status),
            coupon_code=m.coupon_code, created_at=m.created_at,
        )
        for m in models
    ]


class SqlAlchemyOrderRepository(OrderRepository):
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, order_id: int) -> Order | None:
        m = self.db.get(OrderModel, order_id)
        return _to_orders(self.db, [m])[0] if m else None

    def list_for_user(self, user_id: int, page: int, page_size: int):
        return self._paged(select(OrderModel).where(OrderModel.user_id == user_id), page, page_size)

    def list_all(self, status: OrderStatus | None, page: int, page_size: int):
        query = select(OrderModel)
        if status:
            query = query.where(OrderModel.status == status.value)
        return self._paged(query, page, page_size)

    def _paged(self, query, page: int, page_size: int):
        total = self.db.scalar(select(func.count()).select_from(query.subquery()))
        rows = self.db.scalars(
            query.order_by(OrderModel.id.desc()).offset((page - 1) * page_size).limit(page_size)
        ).all()
        return _to_orders(self.db, list(rows)), total


class SqlAlchemyOrderUnitOfWork(OrderUnitOfWork):
    """One database transaction. Nothing is saved until commit() is called."""

    def __init__(self, db: Session):
        self.db = db

    def lock_cart(self, user_id: int) -> Cart:
        cart_row = self.db.scalar(
            select(CartModel).where(CartModel.user_id == user_id).with_for_update()
        )
        if not cart_row:
            return Cart(id=None, user_id=user_id, items=[])
        return SqlAlchemyCartRepository(self.db).get_cart(user_id)

    def find_order_by_key(self, user_id: int, key: str) -> Order | None:
        row = self.db.scalar(
            select(IdempotencyKeyModel).where(
                IdempotencyKeyModel.user_id == user_id, IdempotencyKeyModel.key == key
            )
        )
        if not row:
            return None
        return _to_orders(self.db, [self.db.get(OrderModel, row.order_id)])[0]

    def get_coupon(self, code: str) -> Coupon | None:
        return SqlAlchemyCouponRepository(self.db).get_by_code(code)

    def deduct_stock(self, product_id: int, quantity: int) -> bool:
        # One atomic statement: it only matches while enough stock remains
        result = self.db.execute(
            update(ProductModel)
            .where(ProductModel.id == product_id, ProductModel.stock >= quantity)
            .values(stock=ProductModel.stock - quantity)
        )
        return result.rowcount == 1

    def add_stock(self, product_id: int, quantity: int) -> None:
        self.db.execute(
            update(ProductModel)
            .where(ProductModel.id == product_id)
            .values(stock=ProductModel.stock + quantity)
        )

    def use_coupon(self, coupon_id: int) -> bool:
        result = self.db.execute(
            update(CouponModel)
            .where(CouponModel.id == coupon_id, CouponModel.times_used < CouponModel.max_uses)
            .values(times_used=CouponModel.times_used + 1)
        )
        return result.rowcount == 1

    def create_order(self, order: Order, idempotency_key: str, coupon_id: int | None) -> Order:
        m = OrderModel(
            user_id=order.user_id, status=order.status.value, subtotal=order.subtotal,
            discount=order.discount, total=order.total, coupon_code=order.coupon_code,
        )
        self.db.add(m)
        self.db.flush()  # gives the order its id

        for item in order.items:
            self.db.add(
                OrderItemModel(
                    order_id=m.id, product_id=item.product_id, product_name=item.product_name,
                    unit_price=item.unit_price, quantity=item.quantity,
                )
            )
        self.db.add(IdempotencyKeyModel(user_id=order.user_id, key=idempotency_key, order_id=m.id))
        if coupon_id:
            self.db.add(CouponUsageModel(coupon_id=coupon_id, user_id=order.user_id, order_id=m.id))
        self.db.flush()
        self.db.refresh(m)
        return _to_orders(self.db, [m])[0]

    def clear_cart(self, cart_id: int) -> None:
        self.db.execute(delete(CartItemModel).where(CartItemModel.cart_id == cart_id))

    def lock_order(self, order_id: int) -> Order | None:
        m = self.db.scalar(select(OrderModel).where(OrderModel.id == order_id).with_for_update())
        return _to_orders(self.db, [m])[0] if m else None

    def set_order_status(self, order_id: int, status: OrderStatus) -> None:
        self.db.execute(
            update(OrderModel).where(OrderModel.id == order_id).values(status=status.value)
        )

    def commit(self) -> None:
        self.db.commit()

    def rollback(self) -> None:
        self.db.rollback()



        
    def get_payment_status(self, order_id: int) -> PaymentStatus:
        status = self.db.scalar(
            select(PaymentModel.status)
            .where(PaymentModel.order_id == order_id)
            .order_by(PaymentModel.id.desc())
            .limit(1)
        )
        return PaymentStatus(status) if status else PaymentStatus.NOT_SUBMITTED

    def lock_payment(self, payment_id: int) -> Payment | None:
        m = self.db.scalar(
            select(PaymentModel).where(PaymentModel.id == payment_id).with_for_update()
        )
        return SqlAlchemyPaymentRepository._to_entity(m) if m else None

    def set_payment_review(
        self, payment_id: int, status: PaymentStatus, reviewed_by: int, reason: str | None
    ) -> None:
        self.db.execute(
            update(PaymentModel)
            .where(PaymentModel.id == payment_id)
            .values(
                status=status.value, reviewed_by=reviewed_by,
                reviewed_at=func.now(), rejection_reason=reason,
            )
        )