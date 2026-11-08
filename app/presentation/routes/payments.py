import math

from fastapi import APIRouter, Depends, File, Query, Response, UploadFile, status

from app.application.use_cases.payments import (
    MAX_RECEIPT_BYTES, GetOrderPayment, GetPaymentDetail, GetReceipt,
    ListPayments, ReviewPayment, SubmitPaymentProof,
)
from app.domain.entities import PaymentStatus, Role, User
from app.presentation.dependencies import (
    get_current_user, get_order_repo, get_order_uow, get_payment_repo, require_admin,
)
from app.presentation.schemas import (
    OrderPaymentResponse, OrderResponse, PaginatedPayments, PaymentDetailResponse,
    PaymentResponse, RejectPaymentRequest,
)

router = APIRouter(tags=["Payments"])


# ----- Customer -----
@router.post(
    "/orders/{order_id}/payment", response_model=PaymentResponse, status_code=status.HTTP_201_CREATED
)
def submit_payment_proof(
    order_id: int,
    file: UploadFile = File(..., description="Receipt image: JPG, JPEG or PNG, max 5 MB"),
    current_user: User = Depends(get_current_user),
    orders=Depends(get_order_repo),
    payments=Depends(get_payment_repo),
):
    content = file.file.read(MAX_RECEIPT_BYTES + 1)  # never read more than the limit
    payment = SubmitPaymentProof(orders, payments).execute(current_user.id, order_id, content)
    return PaymentResponse.model_validate(payment)


@router.get("/orders/{order_id}/payment", response_model=OrderPaymentResponse)
def get_order_payment(
    order_id: int,
    current_user: User = Depends(get_current_user),
    orders=Depends(get_order_repo),
    payments=Depends(get_payment_repo),
):
    is_admin = current_user.role == Role.ADMIN
    view = GetOrderPayment(orders, payments).execute(order_id, current_user.id, is_admin)
    return OrderPaymentResponse(
        order_id=view.order_id,
        amount_due=view.amount_due,
        status=view.status,
        payments=[PaymentResponse.model_validate(p) for p in view.payments],
    )


@router.get("/payments/{payment_id}/receipt")
def get_receipt(
    payment_id: int,
    current_user: User = Depends(get_current_user),
    payments=Depends(get_payment_repo),
):
    is_admin = current_user.role == Role.ADMIN
    content, content_type = GetReceipt(payments).execute(payment_id, current_user.id, is_admin)
    extension = "png" if content_type == "image/png" else "jpg"
    return Response(
        content=content,
        media_type=content_type,
        headers={"Content-Disposition": f'inline; filename="receipt-{payment_id}.{extension}"'},
    )


# ----- Admin -----
@router.get("/payments", response_model=PaginatedPayments)
def list_payments(
    payment_status: PaymentStatus | None = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    payments=Depends(get_payment_repo),
    _admin: User = Depends(require_admin),
):
    items, total = ListPayments(payments).execute(payment_status, page, page_size)
    return PaginatedPayments(
        items=[PaymentResponse.model_validate(p) for p in items],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=math.ceil(total / page_size),
    )


@router.get("/payments/{payment_id}", response_model=PaymentDetailResponse)
def get_payment(
    payment_id: int,
    payments=Depends(get_payment_repo),
    orders=Depends(get_order_repo),
    _admin: User = Depends(require_admin),
):
    detail = GetPaymentDetail(payments, orders).execute(payment_id)
    return PaymentDetailResponse(
        payment=PaymentResponse.model_validate(detail.payment),
        order=OrderResponse.model_validate(detail.order),
    )


@router.post("/payments/{payment_id}/approve", response_model=PaymentResponse)
def approve_payment(
    payment_id: int,
    uow=Depends(get_order_uow),
    admin: User = Depends(require_admin),
):
    return PaymentResponse.model_validate(ReviewPayment(uow).approve(payment_id, admin.id))


@router.post("/payments/{payment_id}/reject", response_model=PaymentResponse)
def reject_payment(
    payment_id: int,
    data: RejectPaymentRequest,
    uow=Depends(get_order_uow),
    admin: User = Depends(require_admin),
):
    return PaymentResponse.model_validate(ReviewPayment(uow).reject(payment_id, admin.id, data.reason))