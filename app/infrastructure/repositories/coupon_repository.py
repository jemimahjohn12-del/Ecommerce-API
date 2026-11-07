from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.entities import Coupon, DiscountType
from app.domain.repositories import CouponRepository
from app.infrastructure.models import CouponModel


class SqlAlchemyCouponRepository(CouponRepository):
    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def _to_entity(m: CouponModel) -> Coupon:
        return Coupon(
            id=m.id, code=m.code, discount_type=DiscountType(m.discount_type),
            discount_value=m.discount_value, expires_at=m.expires_at, max_uses=m.max_uses,
            min_order_amount=m.min_order_amount, is_active=m.is_active,
            times_used=m.times_used, created_at=m.created_at,
        )

    def get_by_id(self, coupon_id: int) -> Coupon | None:
        m = self.db.get(CouponModel, coupon_id)
        return self._to_entity(m) if m else None

    def get_by_code(self, code: str) -> Coupon | None:
        m = self.db.scalar(select(CouponModel).where(CouponModel.code == code))
        return self._to_entity(m) if m else None

    def list_all(self) -> list[Coupon]:
        rows = self.db.scalars(select(CouponModel).order_by(CouponModel.id.desc())).all()
        return [self._to_entity(r) for r in rows]

    def add(self, coupon: Coupon) -> Coupon:
        m = CouponModel(
            code=coupon.code, discount_type=coupon.discount_type.value,
            discount_value=coupon.discount_value, expires_at=coupon.expires_at,
            max_uses=coupon.max_uses, min_order_amount=coupon.min_order_amount,
            is_active=coupon.is_active,
        )
        self.db.add(m)
        self.db.commit()
        self.db.refresh(m)
        return self._to_entity(m)

    def update(self, coupon: Coupon) -> Coupon:
        m = self.db.get(CouponModel, coupon.id)
        m.discount_type = coupon.discount_type.value
        m.discount_value = coupon.discount_value
        m.expires_at = coupon.expires_at
        m.max_uses = coupon.max_uses
        m.min_order_amount = coupon.min_order_amount
        m.is_active = coupon.is_active
        self.db.commit()
        self.db.refresh(m)
        return self._to_entity(m)