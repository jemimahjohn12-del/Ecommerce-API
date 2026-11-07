from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.entities import Product
from app.domain.repositories import ProductFilter, ProductRepository
from app.infrastructure.models import ProductModel


class SqlAlchemyProductRepository(ProductRepository):
    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def _to_entity(m: ProductModel) -> Product:
        return Product(
            id=m.id, name=m.name, description=m.description, price=m.price,
            stock=m.stock, sku=m.sku, category_id=m.category_id,
            is_active=m.is_active, created_at=m.created_at,
        )

    def get_by_id(self, product_id: int) -> Product | None:
        m = self.db.get(ProductModel, product_id)
        return self._to_entity(m) if m else None

    def get_by_sku(self, sku: str) -> Product | None:
        m = self.db.scalar(select(ProductModel).where(ProductModel.sku == sku))
        return self._to_entity(m) if m else None

    def search(self, f: ProductFilter) -> tuple[list[Product], int]:
        query = select(ProductModel)

        if not f.include_inactive:
            query = query.where(ProductModel.is_active.is_(True))
        if f.search:
            query = query.where(ProductModel.name.ilike(f"%{f.search}%"))
        if f.category_id is not None:
            query = query.where(ProductModel.category_id == f.category_id)
        if f.min_price is not None:
            query = query.where(ProductModel.price >= f.min_price)
        if f.max_price is not None:
            query = query.where(ProductModel.price <= f.max_price)

        # Count BEFORE adding sorting and paging
        total = self.db.scalar(select(func.count()).select_from(query.subquery()))

        column = ProductModel.price if f.sort_by == "price" else ProductModel.created_at
        column = column.asc() if f.sort_order == "asc" else column.desc()
        query = (
            query.order_by(column, ProductModel.id)
            .offset((f.page - 1) * f.page_size)
            .limit(f.page_size)
        )

        rows = self.db.scalars(query).all()
        return [self._to_entity(r) for r in rows], total

    def add(self, product: Product) -> Product:
        m = ProductModel(
            name=product.name, description=product.description, price=product.price,
            stock=product.stock, sku=product.sku, category_id=product.category_id,
            is_active=product.is_active,
        )
        self.db.add(m)
        self.db.commit()
        self.db.refresh(m)
        return self._to_entity(m)

    def update(self, product: Product) -> Product:
        m = self.db.get(ProductModel, product.id)
        m.name = product.name
        m.description = product.description
        m.price = product.price
        m.stock = product.stock
        m.sku = product.sku
        m.category_id = product.category_id
        m.is_active = product.is_active
        self.db.commit()
        self.db.refresh(m)
        return self._to_entity(m)