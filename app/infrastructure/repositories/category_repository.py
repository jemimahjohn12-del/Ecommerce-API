from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.entities import Category
from app.domain.repositories import CategoryRepository
from app.infrastructure.models import CategoryModel, ProductModel


class SqlAlchemyCategoryRepository(CategoryRepository):
    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def _to_entity(m: CategoryModel) -> Category:
        return Category(id=m.id, name=m.name, description=m.description)

    def get_by_id(self, category_id: int) -> Category | None:
        m = self.db.get(CategoryModel, category_id)
        return self._to_entity(m) if m else None

    def get_by_name(self, name: str) -> Category | None:
        m = self.db.scalar(select(CategoryModel).where(func.lower(CategoryModel.name) == name.lower()))
        return self._to_entity(m) if m else None

    def list_all(self) -> list[Category]:
        rows = self.db.scalars(select(CategoryModel).order_by(CategoryModel.name)).all()
        return [self._to_entity(r) for r in rows]

    def add(self, category: Category) -> Category:
        m = CategoryModel(name=category.name, description=category.description)
        self.db.add(m)
        self.db.commit()
        self.db.refresh(m)
        return self._to_entity(m)

    def update(self, category: Category) -> Category:
        m = self.db.get(CategoryModel, category.id)
        m.name = category.name
        m.description = category.description
        self.db.commit()
        self.db.refresh(m)
        return self._to_entity(m)

    def delete(self, category_id: int) -> None:
        m = self.db.get(CategoryModel, category_id)
        if m:
            self.db.delete(m)
            self.db.commit()

    def has_products(self, category_id: int) -> bool:
        count = self.db.scalar(
            select(func.count()).select_from(ProductModel).where(ProductModel.category_id == category_id)
        )
        return count > 0