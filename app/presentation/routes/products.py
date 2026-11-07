import math
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, Query, status

from app.application.use_cases.products import (
    CreateProduct, DeactivateProduct, GetProduct, ListProducts, UpdateProduct,
)
from app.domain.entities import User
from app.domain.repositories import ProductFilter
from app.presentation.dependencies import get_category_repo, get_product_repo, require_admin
from app.presentation.schemas import (
    PaginatedProducts, ProductCreate, ProductResponse, ProductUpdate, StockUpdate,
)

router = APIRouter(prefix="/products", tags=["Products"])


def product_filters(
    search: str | None = Query(None, min_length=1, description="Search by name"),
    category_id: int | None = Query(None, ge=1),
    min_price: Decimal | None = Query(None, ge=0),
    max_price: Decimal | None = Query(None, ge=0),
    sort_by: Literal["price", "created_at"] = "created_at",
    sort_order: Literal["asc", "desc"] = "desc",
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
) -> ProductFilter:
    return ProductFilter(
        search=search, category_id=category_id, min_price=min_price, max_price=max_price,
        sort_by=sort_by, sort_order=sort_order, page=page, page_size=page_size,
    )


def _paginate(items, total: int, filters: ProductFilter) -> PaginatedProducts:
    return PaginatedProducts(
        items=[ProductResponse.model_validate(p) for p in items],
        total=total,
        page=filters.page,
        page_size=filters.page_size,
        total_pages=math.ceil(total / filters.page_size),
    )


@router.get("", response_model=PaginatedProducts)
def list_products(
    filters: ProductFilter = Depends(product_filters),
    products=Depends(get_product_repo),
):
    items, total = ListProducts(products).execute(filters)
    return _paginate(items, total, filters)


@router.get("/admin/all", response_model=PaginatedProducts)
def list_all_products_admin(
    filters: ProductFilter = Depends(product_filters),
    products=Depends(get_product_repo),
    _admin: User = Depends(require_admin),
):
    filters.include_inactive = True
    items, total = ListProducts(products).execute(filters)
    return _paginate(items, total, filters)


@router.get("/{product_id}", response_model=ProductResponse)
def get_product(product_id: int, products=Depends(get_product_repo)):
    return GetProduct(products).execute(product_id)


@router.post("", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
def create_product(
    data: ProductCreate,
    products=Depends(get_product_repo),
    categories=Depends(get_category_repo),
    _admin: User = Depends(require_admin),
):
    return CreateProduct(products, categories).execute(
        data.name, data.description, data.price, data.stock, data.sku, data.category_id
    )


@router.patch("/{product_id}", response_model=ProductResponse)
def update_product(
    product_id: int,
    data: ProductUpdate,
    products=Depends(get_product_repo),
    categories=Depends(get_category_repo),
    _admin: User = Depends(require_admin),
):
    changes = data.model_dump(exclude_unset=True, exclude_none=True)
    return UpdateProduct(products, categories).execute(product_id, changes)


@router.patch("/{product_id}/stock", response_model=ProductResponse)
def update_stock(
    product_id: int,
    data: StockUpdate,
    products=Depends(get_product_repo),
    categories=Depends(get_category_repo),
    _admin: User = Depends(require_admin),
):
    return UpdateProduct(products, categories).execute(product_id, {"stock": data.stock})


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def deactivate_product(
    product_id: int,
    products=Depends(get_product_repo),
    _admin: User = Depends(require_admin),
):
    DeactivateProduct(products).execute(product_id)