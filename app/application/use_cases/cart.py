from app.domain.entities import Cart, Product
from app.domain.exceptions import InsufficientStock, NotFound
from app.domain.repositories import CartRepository, ProductRepository


def _get_purchasable_product(products: ProductRepository, product_id: int) -> Product:
    product = products.get_by_id(product_id)
    # Customers may only buy active products
    if not product or not product.is_active:
        raise NotFound("Product not found")
    return product


def _check_stock(product: Product, wanted: int) -> None:
    if wanted > product.stock:
        raise InsufficientStock(f"Only {product.stock} unit(s) of '{product.name}' available")


class AddToCart:
    def __init__(self, carts: CartRepository, products: ProductRepository):
        self.carts = carts
        self.products = products

    def execute(self, user_id: int, product_id: int, quantity: int) -> Cart:
        product = _get_purchasable_product(self.products, product_id)

        # Same product again => add to the existing quantity, never a duplicate line
        already_in_cart = self.carts.get_item_quantity(user_id, product_id) or 0
        new_quantity = already_in_cart + quantity
        _check_stock(product, new_quantity)

        self.carts.set_item_quantity(user_id, product_id, new_quantity)
        return self.carts.get_cart(user_id)


class GetCart:
    def __init__(self, carts: CartRepository):
        self.carts = carts

    def execute(self, user_id: int) -> Cart:
        return self.carts.get_cart(user_id)


class UpdateCartItem:
    def __init__(self, carts: CartRepository, products: ProductRepository):
        self.carts = carts
        self.products = products

    def execute(self, user_id: int, product_id: int, quantity: int) -> Cart:
        if self.carts.get_item_quantity(user_id, product_id) is None:
            raise NotFound("Item not found in cart")
        product = _get_purchasable_product(self.products, product_id)
        _check_stock(product, quantity)

        self.carts.set_item_quantity(user_id, product_id, quantity)
        return self.carts.get_cart(user_id)


class RemoveFromCart:
    def __init__(self, carts: CartRepository):
        self.carts = carts

    def execute(self, user_id: int, product_id: int) -> Cart:
        if not self.carts.remove_item(user_id, product_id):
            raise NotFound("Item not found in cart")
        return self.carts.get_cart(user_id)


class ClearCart:
    def __init__(self, carts: CartRepository):
        self.carts = carts

    def execute(self, user_id: int) -> None:
        self.carts.clear(user_id)