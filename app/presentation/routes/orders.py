import math

from fastapi import APIRouter, Depends, Header, Query, Response, status

from app.application.use_cases.orders import (
    CancelOrder, Checkout, GetOrder, ListAllOrders, ListMyOrders, UpdateOrderStatus,
)
from app.domain.entities import OrderStatus, Role, User
from app.presentation.dependencies import (
    get_current_user, get_order_repo, get_order_uow, require_admin,
)
from app.presentation.schemas import (
    CheckoutRequest, OrderResponse, PaginatedOrders, UpdateOrderStatusRequest,
)

router = APIRouter(prefix="/orders", tags=["Orders"])


def _page(orders, total: int, page: int, page_size: int) -> PaginatedOrders:
    return PaginatedOrders(
        items=[OrderResponse.model_validate(o) for o in orders],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=math.ceil(total / page_size),
    )


@router.post("/checkout", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
def checkout(
    response: Response,
    idempotency_key: str = Header(
        min_length=8, max_length=100, description="Unique value per checkout attempt"
    ),
    data: CheckoutRequest | None = None,
    current_user: User = Depends(get_current_user),
    uow=Depends(get_order_uow),
):
    coupon_code = data.coupon_code if data else None
    order, created = Checkout(uow).execute(current_user.id, idempotency_key, coupon_code)
    if not created:
        response.status_code = status.HTTP_200_OK  # same key again: the original order
    return OrderResponse.model_validate(order)


@router.get("", response_model=PaginatedOrders)
def my_orders(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    orders=Depends(get_order_repo),
):
    items, total = ListMyOrders(orders).execute(current_user.id, page, page_size)
    return _page(items, total, page, page_size)


@router.get("/admin/all", response_model=PaginatedOrders)
def all_orders(
    order_status: OrderStatus | None = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    orders=Depends(get_order_repo),
    _admin: User = Depends(require_admin),
):
    items, total = ListAllOrders(orders).execute(order_status, page, page_size)
    return _page(items, total, page, page_size)


@router.get("/{order_id}", response_model=OrderResponse)
def get_order(
    order_id: int,
    current_user: User = Depends(get_current_user),
    orders=Depends(get_order_repo),
):
    is_admin = current_user.role == Role.ADMIN
    order = GetOrder(orders).execute(order_id, current_user.id, is_admin)
    return OrderResponse.model_validate(order)


@router.post("/{order_id}/cancel", response_model=OrderResponse)
def cancel_order(
    order_id: int,
    current_user: User = Depends(get_current_user),
    uow=Depends(get_order_uow),
):
    order = CancelOrder(uow).execute(current_user.id, order_id)
    return OrderResponse.model_validate(order)


@router.patch("/{order_id}/status", response_model=OrderResponse)
def update_status(
    order_id: int,
    data: UpdateOrderStatusRequest,
    uow=Depends(get_order_uow),
    _admin: User = Depends(require_admin),
):
    order = UpdateOrderStatus(uow).execute(order_id, data.status)
    return OrderResponse.model_validate(order)