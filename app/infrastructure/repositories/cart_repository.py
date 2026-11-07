from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domain.entities import Cart, CartItem
from app.domain.repositories import CartRepository
from app.infrastructure.models import CartItemModel, CartModel, ProductModel


class SqlAlchemyCartRepository(CartRepository):
    def __init__(self, db: Session):
        self.db = db

    def _get_or_create_cart(self, user_id: int) -> CartModel:
        cart = self.db.scalar(select(CartModel).where(CartModel.user_id == user_id))
        if cart:
            return cart
        try:
            cart = CartModel(user_id=user_id)
            self.db.add(cart)
            self.db.commit()
            self.db.refresh(cart)
            return cart
        except IntegrityError:
            # Two requests created the cart at the same moment; use the one that won
            self.db.rollback()
            return self.db.scalar(select(CartModel).where(CartModel.user_id == user_id))

    def _find_item(self, cart_id: int, product_id: int) -> CartItemModel | None:
        return self.db.scalar(
            select(CartItemModel).where(
                CartItemModel.cart_id == cart_id,
                CartItemModel.product_id == product_id,
            )
        )

    def get_cart(self, user_id: int) -> Cart:
        cart = self._get_or_create_cart(user_id)
        rows = self.db.execute(
            select(
                CartItemModel.product_id,
                CartItemModel.quantity,
                ProductModel.name,
                ProductModel.price,
                ProductModel.stock,
                ProductModel.is_active,
            )
            .join(ProductModel, ProductModel.id == CartItemModel.product_id)
            .where(CartItemModel.cart_id == cart.id)
            .order_by(CartItemModel.id)
        ).all()

        items = [
            CartItem(
                product_id=r.product_id,
                product_name=r.name,
                unit_price=r.price,
                quantity=r.quantity,
                available_stock=r.stock,
                product_is_active=r.is_active,
            )
            for r in rows
        ]
        return Cart(id=cart.id, user_id=user_id, items=items)

    def get_item_quantity(self, user_id: int, product_id: int) -> int | None:
        cart = self._get_or_create_cart(user_id)
        item = self._find_item(cart.id, product_id)
        return item.quantity if item else None

    def set_item_quantity(self, user_id: int, product_id: int, quantity: int) -> None:
        cart = self._get_or_create_cart(user_id)
        item = self._find_item(cart.id, product_id)
        if item:
            item.quantity = quantity
        else:
            self.db.add(CartItemModel(cart_id=cart.id, product_id=product_id, quantity=quantity))
        self.db.commit()

    def remove_item(self, user_id: int, product_id: int) -> bool:
        cart = self._get_or_create_cart(user_id)
        item = self._find_item(cart.id, product_id)
        if not item:
            return False
        self.db.delete(item)
        self.db.commit()
        return True

    def clear(self, user_id: int) -> None:
        cart = self._get_or_create_cart(user_id)
        self.db.execute(delete(CartItemModel).where(CartItemModel.cart_id == cart.id))
        self.db.commit()