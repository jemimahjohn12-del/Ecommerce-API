from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

from app.domain.entities import Coupon
from app.domain.exceptions import CouponAlreadyExists, InvalidData, NotFound
from app.domain.repositories import CartRepository, CouponRepository


@dataclass
class AppliedCoupon:
    code: str
    subtotal: Decimal
    discount: Decimal
    final_total: Decimal


class CreateCoupon:
    def __init__(self, coupons: CouponRepository):
        self.coupons = coupons

    def execute(
        self, code, discount_type, discount_value, expires_at, max_uses, min_order_amount, is_active
    ) -> Coupon:
        code = code.strip().upper()
        if self.coupons.get_by_code(code):
            raise CouponAlreadyExists("A coupon with this code already exists")
        coupon = Coupon(
            id=None, code=code, discount_type=discount_type, discount_value=discount_value,
            expires_at=expires_at, max_uses=max_uses, min_order_amount=min_order_amount,
            is_active=is_active,
        )  # the Coupon itself checks the business rules
        return self.coupons.add(coupon)


class ListCoupons:
    def __init__(self, coupons: CouponRepository):
        self.coupons = coupons

    def execute(self) -> list[Coupon]:
        return self.coupons.list_all()


class GetCoupon:
    def __init__(self, coupons: CouponRepository):
        self.coupons = coupons

    def execute(self, coupon_id: int) -> Coupon:
        coupon = self.coupons.get_by_id(coupon_id)
        if not coupon:
            raise NotFound("Coupon not found")
        return coupon


class UpdateCoupon:
    def __init__(self, coupons: CouponRepository):
        self.coupons = coupons

    def execute(self, coupon_id: int, changes: dict) -> Coupon:
        coupon = self.coupons.get_by_id(coupon_id)
        if not coupon:
            raise NotFound("Coupon not found")
        for field, value in changes.items():
            setattr(coupon, field, value)
        coupon.validate()
        return self.coupons.update(coupon)


class ApplyCoupon:
    """Preview: checks a code against the customer's cart. Usage is counted at checkout."""

    def __init__(self, coupons: CouponRepository, carts: CartRepository):
        self.coupons = coupons
        self.carts = carts

    def execute(self, user_id: int, code: str) -> AppliedCoupon:
        coupon = self.coupons.get_by_code(code.strip().upper())
        if not coupon:
            raise NotFound("Coupon not found")

        cart = self.carts.get_cart(user_id)
        if not cart.items:
            raise InvalidData("Your cart is empty")

        subtotal = cart.total
        coupon.check_usable(subtotal, datetime.now(timezone.utc))
        discount = coupon.calculate_discount(subtotal)
        return AppliedCoupon(
            code=coupon.code, subtotal=subtotal, discount=discount,
            final_total=subtotal - discount,
        )