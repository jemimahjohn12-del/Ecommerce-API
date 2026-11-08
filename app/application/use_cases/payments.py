from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

from app.application.interfaces import OrderUnitOfWork
from app.domain.entities import Order, OrderStatus, Payment, PaymentStatus
from app.domain.exceptions import InvalidData, InvalidStatusTransition, NotFound
from app.domain.repositories import OrderRepository, PaymentRepository

MAX_RECEIPT_BYTES = 5 * 1024 * 1024  # 5 MB


def detect_image_type(content: bytes) -> str | None:
    """Look at the file's real content, not its name or what the client claims."""
    if content.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    return None


@dataclass
class OrderPaymentView:
    order_id: int
    amount_due: Decimal
    status: PaymentStatus
    payments: list[Payment]


@dataclass
class PaymentDetail:
    payment: Payment
    order: Order


class SubmitPaymentProof:
    def __init__(self, orders: OrderRepository, payments: PaymentRepository):
        self.orders = orders
        self.payments = payments

    def execute(self, user_id: int, order_id: int, content: bytes) -> Payment:
        order = self.orders.get_by_id(order_id)
        if not order or order.user_id != user_id:
            raise NotFound("Order not found")
        if order.status != OrderStatus.PENDING:
            raise InvalidStatusTransition(
                f"Payment cannot be submitted for an order that is {order.status.value}"
            )

        latest = self.payments.get_latest_for_order(order.id)
        if latest and latest.status in (PaymentStatus.UNDER_REVIEW, PaymentStatus.APPROVED):
            raise InvalidStatusTransition(f"A payment for this order is already {latest.status.value}")

        if not content:
            raise InvalidData("The file is empty")
        if len(content) > MAX_RECEIPT_BYTES:
            raise InvalidData("File is too large (maximum 5 MB)")
        content_type = detect_image_type(content)
        if not content_type:
            raise InvalidData("Only JPG, JPEG or PNG images are accepted")

        payment = Payment(
            id=None, order_id=order.id, user_id=user_id,
            amount=order.total, content_type=content_type,
        )
        return self.payments.add(payment, content)


class GetOrderPayment:
    def __init__(self, orders: OrderRepository, payments: PaymentRepository):
        self.orders = orders
        self.payments = payments

    def execute(self, order_id: int, user_id: int, is_admin: bool) -> OrderPaymentView:
        order = self.orders.get_by_id(order_id)
        if not order or (not is_admin and order.user_id != user_id):
            raise NotFound("Order not found")
        history = self.payments.list_for_order(order.id)  # newest first
        status = history[0].status if history else PaymentStatus.NOT_SUBMITTED
        return OrderPaymentView(order.id, order.total, status, history)


class ListPayments:
    def __init__(self, payments: PaymentRepository):
        self.payments = payments

    def execute(self, status: PaymentStatus | None, page: int, page_size: int):
        return self.payments.list_all(status, page, page_size)


class GetPaymentDetail:
    def __init__(self, payments: PaymentRepository, orders: OrderRepository):
        self.payments = payments
        self.orders = orders

    def execute(self, payment_id: int) -> PaymentDetail:
        payment = self.payments.get_by_id(payment_id)
        if not payment:
            raise NotFound("Payment not found")
        return PaymentDetail(payment=payment, order=self.orders.get_by_id(payment.order_id))


class GetReceipt:
    def __init__(self, payments: PaymentRepository):
        self.payments = payments

    def execute(self, payment_id: int, user_id: int, is_admin: bool) -> tuple[bytes, str]:
        payment = self.payments.get_by_id(payment_id)
        if not payment or (not is_admin and payment.user_id != user_id):
            raise NotFound("Payment not found")
        content = self.payments.get_receipt(payment_id)
        if content is None:
            raise NotFound("Receipt not found")
        return content, payment.content_type


class ReviewPayment:
    def __init__(self, uow: OrderUnitOfWork):
        self.uow = uow

    def approve(self, payment_id: int, admin_id: int) -> Payment:
        return self._review(payment_id, admin_id, PaymentStatus.APPROVED, None)

    def reject(self, payment_id: int, admin_id: int, reason: str) -> Payment:
        reason = reason.strip()
        if len(reason) < 3:
            raise InvalidData("A reason is required when rejecting a payment")
        return self._review(payment_id, admin_id, PaymentStatus.REJECTED, reason)

    def _review(
        self, payment_id: int, admin_id: int, new_status: PaymentStatus, reason: str | None
    ) -> Payment:
        try:
            payment = self.uow.lock_payment(payment_id)  # locked: two admins can't both review
            if not payment:
                raise NotFound("Payment not found")
            payment.ensure_reviewable()

            order = self.uow.lock_order(payment.order_id)
            if new_status == PaymentStatus.APPROVED:
                if not order or order.status == OrderStatus.CANCELLED:
                    raise InvalidStatusTransition("Cannot approve a payment for a cancelled order")

            self.uow.set_payment_review(payment_id, new_status, admin_id, reason)
            if new_status == PaymentStatus.APPROVED and order.status == OrderStatus.PENDING:
                self.uow.set_order_status(order.id, OrderStatus.CONFIRMED)

            self.uow.commit()
            payment.status = new_status
            payment.rejection_reason = reason
            payment.reviewed_by = admin_id
            payment.reviewed_at = datetime.now(timezone.utc)
            return payment
        except Exception:
            self.uow.rollback()
            raise