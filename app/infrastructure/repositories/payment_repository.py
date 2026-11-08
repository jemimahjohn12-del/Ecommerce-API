from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domain.entities import Payment, PaymentStatus
from app.domain.exceptions import InvalidStatusTransition
from app.domain.repositories import PaymentRepository
from app.infrastructure.models import PaymentModel, PaymentReceiptModel


class SqlAlchemyPaymentRepository(PaymentRepository):
    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def _to_entity(m: PaymentModel) -> Payment:
        return Payment(
            id=m.id, order_id=m.order_id, user_id=m.user_id, amount=m.amount,
            content_type=m.content_type, status=PaymentStatus(m.status),
            rejection_reason=m.rejection_reason, reviewed_by=m.reviewed_by,
            reviewed_at=m.reviewed_at, submitted_at=m.submitted_at,
        )

    def get_by_id(self, payment_id: int) -> Payment | None:
        m = self.db.get(PaymentModel, payment_id)
        return self._to_entity(m) if m else None

    def get_latest_for_order(self, order_id: int) -> Payment | None:
        m = self.db.scalar(
            select(PaymentModel)
            .where(PaymentModel.order_id == order_id)
            .order_by(PaymentModel.id.desc())
            .limit(1)
        )
        return self._to_entity(m) if m else None

    def list_for_order(self, order_id: int) -> list[Payment]:
        rows = self.db.scalars(
            select(PaymentModel)
            .where(PaymentModel.order_id == order_id)
            .order_by(PaymentModel.id.desc())
        ).all()
        return [self._to_entity(r) for r in rows]

    def list_all(self, status: PaymentStatus | None, page: int, page_size: int):
        query = select(PaymentModel)
        if status:
            query = query.where(PaymentModel.status == status.value)
        total = self.db.scalar(select(func.count()).select_from(query.subquery()))
        rows = self.db.scalars(
            query.order_by(PaymentModel.id.desc()).offset((page - 1) * page_size).limit(page_size)
        ).all()
        return [self._to_entity(r) for r in rows], total

    def add(self, payment: Payment, receipt: bytes) -> Payment:
        m = PaymentModel(
            order_id=payment.order_id, user_id=payment.user_id, amount=payment.amount,
            status=payment.status.value, content_type=payment.content_type,
        )
        try:
            self.db.add(m)
            self.db.flush()
            self.db.add(PaymentReceiptModel(payment_id=m.id, content=receipt))
            self.db.commit()
        except IntegrityError:
            # The partial unique index caught a second active payment for this order
            self.db.rollback()
            raise InvalidStatusTransition("A payment for this order is already under review or approved")
        self.db.refresh(m)
        return self._to_entity(m)

    def get_receipt(self, payment_id: int) -> bytes | None:
        return self.db.scalar(
            select(PaymentReceiptModel.content).where(PaymentReceiptModel.payment_id == payment_id)
        )