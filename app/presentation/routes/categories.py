from fastapi import APIRouter, Depends, status

from app.application.use_cases.categories import (
    CreateCategory, DeleteCategory, GetCategory, ListCategories, UpdateCategory,
)
from app.domain.entities import User
from app.presentation.dependencies import get_category_repo, require_admin
from app.presentation.schemas import CategoryCreate, CategoryResponse, CategoryUpdate

router = APIRouter(prefix="/categories", tags=["Categories"])


@router.get("", response_model=list[CategoryResponse])
def list_categories(categories=Depends(get_category_repo)):
    return ListCategories(categories).execute()


@router.get("/{category_id}", response_model=CategoryResponse)
def get_category(category_id: int, categories=Depends(get_category_repo)):
    return GetCategory(categories).execute(category_id)


@router.post("", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED)
def create_category(
    data: CategoryCreate,
    categories=Depends(get_category_repo),
    _admin: User = Depends(require_admin),
):
    return CreateCategory(categories).execute(data.name, data.description)


@router.put("/{category_id}", response_model=CategoryResponse)
def update_category(
    category_id: int,
    data: CategoryUpdate,
    categories=Depends(get_category_repo),
    _admin: User = Depends(require_admin),
):
    changes = data.model_dump(exclude_unset=True, exclude_none=True)
    return UpdateCategory(categories).execute(category_id, changes)


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_category(
    category_id: int,
    categories=Depends(get_category_repo),
    _admin: User = Depends(require_admin),
):
    DeleteCategory(categories).execute(category_id)