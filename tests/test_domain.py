from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.application.use_cases.payments import detect_image_type
from app.domain.entities import (
    Cart, CartItem, Coupon, DiscountType, Order, OrderStatus, Product,
)
from app.domain.exceptions import CouponNotValid, InvalidData, InvalidStatusTransition

NOW = datetime.now(timezone.utc)
FUTURE = NOW + timedelta(days=30)
PAST = NOW - timedelta(days=1)


def build_coupon(**overrides) -> Coupon:
    values = dict(
        id=1, code="SAVE", discount_type=DiscountType.PERCENTAGE,
        discount_value=Decimal("10"), expires_at=FUTURE, max_uses=5,
    )
    values.update(overrides)
    return Coupon(**values)


def build_order(status=OrderStatus.PENDING) -> Order:
    return Order(
        id=1, user_id=1, items=[], subtotal=Decimal("10"),
        discount=Decimal("0"), total=Decimal("10"), status=status,
    )


# ---------- Coupon calculations ----------
def test_percentage_discount():
    assert build_coupon().calculate_discount(Decimal("200.00")) == Decimal("20.00")


def test_percentage_discount_rounds_to_cents():
    coupon = build_coupon(discount_value=Decimal("15"))
    assert coupon.calculate_discount(Decimal("33.33")) == Decimal("5.00")


def test_fixed_discount():
    coupon = build_coupon(discount_type=DiscountType.FIXED, discount_value=Decimal("5"))
    assert coupon.calculate_discount(Decimal("50.00")) == Decimal("5")


def test_discount_never_makes_total_negative():
    coupon = build_coupon(discount_type=DiscountType.FIXED, discount_value=Decimal("500"))
    total = Decimal("40.00")
    discount = coupon.calculate_discount(total)
    assert discount == total
    assert total - discount == 0


@pytest.mark.parametrize("value", ["0", "-5"])
def test_discount_value_must_be_positive(value):
    with pytest.raises(InvalidData):
        build_coupon(discount_value=Decimal(value))


def test_percentage_cannot_exceed_100():
    with pytest.raises(InvalidData):
        build_coupon(discount_value=Decimal("150"))


def test_usage_limit_must_be_at_least_one():
    with pytest.raises(InvalidData):
        build_coupon(max_uses=0)


# ---------- Coupon rules ----------
def test_expired_coupon_is_rejected():
    with pytest.raises(CouponNotValid, match="expired"):
        build_coupon(expires_at=PAST).check_usable(Decimal("100"), NOW)


def test_inactive_coupon_is_rejected():
    with pytest.raises(CouponNotValid, match="inactive"):
        build_coupon(is_active=False).check_usable(Decimal("100"), NOW)


def test_coupon_cannot_exceed_usage_limit():
    with pytest.raises(CouponNotValid, match="usage limit"):
        build_coupon(times_used=5, max_uses=5).check_usable(Decimal("100"), NOW)


def test_minimum_order_amount_is_enforced():
    coupon = build_coupon(min_order_amount=Decimal("50"))
    with pytest.raises(CouponNotValid, match="Minimum order amount"):
        coupon.check_usable(Decimal("40"), NOW)


def test_valid_coupon_passes():
    build_coupon().check_usable(Decimal("100"), NOW)


# ---------- Product rules ----------
def build_product(**overrides) -> Product:
    values = dict(
        id=None, name="Mouse", description=None, price=Decimal("10"),
        stock=5, sku="M-1", category_id=1,
    )
    values.update(overrides)
    return Product(**values)


def test_product_price_must_be_positive():
    with pytest.raises(InvalidData):
        build_product(price=Decimal("0"))


def test_product_stock_cannot_be_negative():
    with pytest.raises(InvalidData):
        build_product(stock=-1)


# ---------- Order status rules ----------
@pytest.mark.parametrize(
    "current,new",
    [
        (OrderStatus.PENDING, OrderStatus.CONFIRMED),
        (OrderStatus.PENDING, OrderStatus.CANCELLED),
        (OrderStatus.CONFIRMED, OrderStatus.PROCESSING),
        (OrderStatus.PROCESSING, OrderStatus.SHIPPED),
        (OrderStatus.SHIPPED, OrderStatus.DELIVERED),
    ],
)
def test_valid_status_transitions(current, new):
    build_order(current).ensure_transition(new)


@pytest.mark.parametrize(
    "current,new",
    [
        (OrderStatus.DELIVERED, OrderStatus.CANCELLED),
        (OrderStatus.PENDING, OrderStatus.SHIPPED),
        (OrderStatus.CANCELLED, OrderStatus.PENDING),
        (OrderStatus.SHIPPED, OrderStatus.CANCELLED),
    ],
)
def test_invalid_status_transitions(current, new):
    with pytest.raises(InvalidStatusTransition):
        build_order(current).ensure_transition(new)


@pytest.mark.parametrize("status", [OrderStatus.PENDING, OrderStatus.CONFIRMED])
def test_customer_can_cancel_early_orders(status):
    build_order(status).ensure_customer_can_cancel()


@pytest.mark.parametrize(
    "status",
    [OrderStatus.PROCESSING, OrderStatus.SHIPPED, OrderStatus.DELIVERED, OrderStatus.CANCELLED],
)
def test_customer_cannot_cancel_late_orders(status):
    with pytest.raises(InvalidStatusTransition):
        build_order(status).ensure_customer_can_cancel()


def test_order_total_cannot_be_negative():
    with pytest.raises(InvalidData):
        Order(
            id=1, user_id=1, items=[], subtotal=Decimal("10"),
            discount=Decimal("0"), total=Decimal("-1"),
        )


# ---------- Cart ----------
def test_cart_total_and_availability():
    items = [
        CartItem(product_id=1, product_name="A", unit_price=Decimal("2.50"), quantity=2,
                 available_stock=5, product_is_active=True),
        CartItem(product_id=2, product_name="B", unit_price=Decimal("10.00"), quantity=3,
                 available_stock=1, product_is_active=True),
    ]
    cart = Cart(id=1, user_id=1, items=items)
    assert cart.total == Decimal("35.00")
    assert cart.item_count == 5
    assert items[0].is_available is True
    assert items[1].is_available is False


# ---------- Receipt file check ----------
def test_detect_image_type():
    assert detect_image_type(b"\x89PNG\r\n\x1a\n" + b"data") == "image/png"
    assert detect_image_type(b"\xff\xd8\xff\xe0" + b"data") == "image/jpeg"
    assert detect_image_type(b"just some text") is None
    assert detect_image_type(b"") is None