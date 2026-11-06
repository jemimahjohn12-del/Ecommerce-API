from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.entities import Role, User
from app.domain.repositories import UserRepository
from app.infrastructure.models import UserModel


class SqlAlchemyUserRepository(UserRepository):
    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def _to_entity(m: UserModel) -> User:
        return User(
            id=m.id, email=m.email, full_name=m.full_name,
            hashed_password=m.hashed_password, role=Role(m.role), is_active=m.is_active,
        )

    def get_by_email(self, email: str) -> User | None:
        m = self.db.scalar(select(UserModel).where(UserModel.email == email))
        return self._to_entity(m) if m else None

    def get_by_id(self, user_id: int) -> User | None:
        m = self.db.get(UserModel, user_id)
        return self._to_entity(m) if m else None

    def add(self, user: User) -> User:
        m = UserModel(
            email=user.email, full_name=user.full_name,
            hashed_password=user.hashed_password, role=user.role.value,
            is_active=user.is_active,
        )
        self.db.add(m)
        self.db.commit()
        self.db.refresh(m)
        return self._to_entity(m)