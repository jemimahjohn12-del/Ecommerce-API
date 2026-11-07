from fastapi import APIRouter, Depends, status

from app.application.use_cases.coupons import (
    ApplyCoupon, CreateCoupon, GetCoupon, ListCoupons, UpdateCoupon,
)
from app.domain.entities import User
from app.presentation.dependencies import (
    get_cart_repo, get_coupon_repo, get_current_user, require_admin,
)
from app.presentation.schemas import (
    AppliedCouponResponse, ApplyCouponRequest, CouponCreate, CouponResponse, CouponUpdate,
)

router = APIRouter(prefix="/coupons", tags=["Coupons"])


# ----- Customer -----
@router.post("/apply", response_model=AppliedCouponResponse)
def apply_coupon(
    data: ApplyCouponRequest,
    current_user: User = Depends(get_current_user),
    coupons=Depends(get_coupon_repo),
    carts=Depends(get_cart_repo),
):
    result = ApplyCoupon(coupons, carts).execute(current_user.id, data.code)
    return AppliedCouponResponse(
        code=result.code, subtotal=result.subtotal,
        discount=result.discount, final_total=result.final_total,
    )


# ----- Admin -----
@router.post("", response_model=CouponResponse, status_code=status.HTTP_201_CREATED)
def create_coupon(
    data: CouponCreate,
    coupons=Depends(get_coupon_repo),
    _admin: User = Depends(require_admin),
):
    coupon = CreateCoupon(coupons).execute(
        data.code, data.discount_type, data.discount_value, data.expires_at,
        data.max_uses, data.min_order_amount, data.is_active,
    )
    return CouponResponse.model_validate(coupon)


@router.get("", response_model=list[CouponResponse])
def list_coupons(coupons=Depends(get_coupon_repo), _admin: User = Depends(require_admin)):
    return [CouponResponse.model_validate(c) for c in ListCoupons(coupons).execute()]


@router.get("/{coupon_id}", response_model=CouponResponse)
def get_coupon(
    coupon_id: int,
    coupons=Depends(get_coupon_repo),
    _admin: User = Depends(require_admin),
):
    return CouponResponse.model_validate(GetCoupon(coupons).execute(coupon_id))


@router.patch("/{coupon_id}", response_model=CouponResponse)
def update_coupon(
    coupon_id: int,
    data: CouponUpdate,
    coupons=Depends(get_coupon_repo),
    _admin: User = Depends(require_admin),
):
    changes = data.model_dump(exclude_unset=True, exclude_none=True)
    return CouponResponse.model_validate(UpdateCoupon(coupons).execute(coupon_id, changes))