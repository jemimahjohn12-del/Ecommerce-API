from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.domain.entities import Role, User
from app.domain.exceptions import InvalidCredentials
from app.infrastructure.database import SessionLocal
from app.infrastructure.repositories.category_repository import SqlAlchemyCategoryRepository
from app.infrastructure.repositories.product_repository import SqlAlchemyProductRepository
from app.infrastructure.repositories.user_repository import SqlAlchemyUserRepository
from app.infrastructure.security import BcryptPasswordHasher, JWTTokenService
from app.infrastructure.repositories.cart_repository import SqlAlchemyCartRepository
from app.infrastructure.repositories.coupon_repository import SqlAlchemyCouponRepository
from app.infrastructure.repositories.order_repository import (
    SqlAlchemyOrderRepository, SqlAlchemyOrderUnitOfWork,
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_user_repo(db: Session = Depends(get_db)) -> SqlAlchemyUserRepository:
    return SqlAlchemyUserRepository(db)


def get_category_repo(db: Session = Depends(get_db)) -> SqlAlchemyCategoryRepository:
    return SqlAlchemyCategoryRepository(db)


def get_product_repo(db: Session = Depends(get_db)) -> SqlAlchemyProductRepository:
    return SqlAlchemyProductRepository(db)

def get_cart_repo(db: Session = Depends(get_db)) -> SqlAlchemyCartRepository:
    return SqlAlchemyCartRepository(db)

def get_coupon_repo(db: Session = Depends(get_db)) -> SqlAlchemyCouponRepository:
    return SqlAlchemyCouponRepository(db)

def get_order_repo(db: Session = Depends(get_db)) -> SqlAlchemyOrderRepository:
    return SqlAlchemyOrderRepository(db)


def get_order_uow(db: Session = Depends(get_db)) -> SqlAlchemyOrderUnitOfWork:
    return SqlAlchemyOrderUnitOfWork(db)

def get_hasher() -> BcryptPasswordHasher:
    return BcryptPasswordHasher()


def get_token_service() -> JWTTokenService:
    return JWTTokenService()


def get_current_user(
    token: str = Depends(oauth2_scheme),
    users: SqlAlchemyUserRepository = Depends(get_user_repo),
    tokens: JWTTokenService = Depends(get_token_service),
) -> User:
    try:
        user_id = tokens.decode_token(token)
    except InvalidCredentials as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = users.get_by_id(user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != Role.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return user