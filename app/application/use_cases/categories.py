from app.domain.entities import Category
from app.domain.exceptions import CategoryAlreadyExists, CategoryInUse, NotFound
from app.domain.repositories import CategoryRepository


class CreateCategory:
    def __init__(self, categories: CategoryRepository):
        self.categories = categories

    def execute(self, name: str, description: str | None) -> Category:
        name = name.strip()
        if self.categories.get_by_name(name):
            raise CategoryAlreadyExists("A category with this name already exists")
        return self.categories.add(Category(id=None, name=name, description=description))


class ListCategories:
    def __init__(self, categories: CategoryRepository):
        self.categories = categories

    def execute(self) -> list[Category]:
        return self.categories.list_all()


class GetCategory:
    def __init__(self, categories: CategoryRepository):
        self.categories = categories

    def execute(self, category_id: int) -> Category:
        category = self.categories.get_by_id(category_id)
        if not category:
            raise NotFound("Category not found")
        return category


class UpdateCategory:
    def __init__(self, categories: CategoryRepository):
        self.categories = categories

    def execute(self, category_id: int, changes: dict) -> Category:
        category = self.categories.get_by_id(category_id)
        if not category:
            raise NotFound("Category not found")

        if "name" in changes:
            new_name = changes["name"].strip()
            other = self.categories.get_by_name(new_name)
            if other and other.id != category.id:
                raise CategoryAlreadyExists("A category with this name already exists")
            category.name = new_name
        if "description" in changes:
            category.description = changes["description"]

        return self.categories.update(category)


class DeleteCategory:
    def __init__(self, categories: CategoryRepository):
        self.categories = categories

    def execute(self, category_id: int) -> None:
        if not self.categories.get_by_id(category_id):
            raise NotFound("Category not found")
        if self.categories.has_products(category_id):
            raise CategoryInUse("Cannot delete a category that still has products")
        self.categories.delete(category_id)