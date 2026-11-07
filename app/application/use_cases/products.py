from app.domain.entities import Product
from app.domain.exceptions import InvalidData, NotFound, SkuAlreadyExists
from app.domain.repositories import CategoryRepository, ProductFilter, ProductRepository


class CreateProduct:
    def __init__(self, products: ProductRepository, categories: CategoryRepository):
        self.products = products
        self.categories = categories

    def execute(
        self, name: str, description: str | None, price, stock: int, sku: str, category_id: int
    ) -> Product:
        sku = sku.strip().upper()
        if self.products.get_by_sku(sku):
            raise SkuAlreadyExists("A product with this SKU already exists")
        if not self.categories.get_by_id(category_id):
            raise NotFound("Category not found")

        product = Product(
            id=None, name=name.strip(), description=description,
            price=price, stock=stock, sku=sku, category_id=category_id,
        )
        return self.products.add(product)


class GetProduct:
    def __init__(self, products: ProductRepository):
        self.products = products

    def execute(self, product_id: int, include_inactive: bool = False) -> Product:
        product = self.products.get_by_id(product_id)
        # Customers must not see deactivated products
        if not product or (not product.is_active and not include_inactive):
            raise NotFound("Product not found")
        return product


class ListProducts:
    def __init__(self, products: ProductRepository):
        self.products = products

    def execute(self, filters: ProductFilter) -> tuple[list[Product], int]:
        if (
            filters.min_price is not None
            and filters.max_price is not None
            and filters.min_price > filters.max_price
        ):
            raise InvalidData("min_price cannot be greater than max_price")
        return self.products.search(filters)


class UpdateProduct:
    def __init__(self, products: ProductRepository, categories: CategoryRepository):
        self.products = products
        self.categories = categories

    def execute(self, product_id: int, changes: dict) -> Product:
        product = self.products.get_by_id(product_id)
        if not product:
            raise NotFound("Product not found")

        if "sku" in changes:
            changes["sku"] = changes["sku"].strip().upper()
            other = self.products.get_by_sku(changes["sku"])
            if other and other.id != product.id:
                raise SkuAlreadyExists("A product with this SKU already exists")
        if "category_id" in changes and not self.categories.get_by_id(changes["category_id"]):
            raise NotFound("Category not found")
        if "name" in changes:
            changes["name"] = changes["name"].strip()

        for field, value in changes.items():
            setattr(product, field, value)
        product.validate()  # re-check price > 0 and stock >= 0
        return self.products.update(product)


class DeactivateProduct:
    def __init__(self, products: ProductRepository):
        self.products = products

    def execute(self, product_id: int) -> None:
        product = self.products.get_by_id(product_id)
        if not product:
            raise NotFound("Product not found")
        product.is_active = False
        self.products.update(product)