from fastapi import APIRouter, Depends, status

from app.application.use_cases.cart import (
    AddToCart, ClearCart, GetCart, RemoveFromCart, UpdateCartItem,
)
from app.domain.entities import Cart, User
from app.presentation.dependencies import get_cart_repo, get_current_user, get_product_repo
from app.presentation.schemas import AddToCartRequest, CartResponse, UpdateCartItemRequest

router = APIRouter(prefix="/cart", tags=["Shopping Cart"])


def _to_response(cart: Cart) -> CartResponse:
    return CartResponse.model_validate(cart)


@router.get("", response_model=CartResponse)
def view_cart(
    current_user: User = Depends(get_current_user),
    carts=Depends(get_cart_repo),
):
    return _to_response(GetCart(carts).execute(current_user.id))


@router.post("/items", response_model=CartResponse)
def add_to_cart(
    data: AddToCartRequest,
    current_user: User = Depends(get_current_user),
    carts=Depends(get_cart_repo),
    products=Depends(get_product_repo),
):
    cart = AddToCart(carts, products).execute(current_user.id, data.product_id, data.quantity)
    return _to_response(cart)


@router.put("/items/{product_id}", response_model=CartResponse)
def update_cart_item(
    product_id: int,
    data: UpdateCartItemRequest,
    current_user: User = Depends(get_current_user),
    carts=Depends(get_cart_repo),
    products=Depends(get_product_repo),
):
    cart = UpdateCartItem(carts, products).execute(current_user.id, product_id, data.quantity)
    return _to_response(cart)


@router.delete("/items/{product_id}", response_model=CartResponse)
def remove_from_cart(
    product_id: int,
    current_user: User = Depends(get_current_user),
    carts=Depends(get_cart_repo),
):
    return _to_response(RemoveFromCart(carts).execute(current_user.id, product_id))


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
def clear_cart(
    current_user: User = Depends(get_current_user),
    carts=Depends(get_cart_repo),
):
    ClearCart(carts).execute(current_user.id)