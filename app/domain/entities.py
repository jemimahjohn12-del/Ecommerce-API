from dataclasses import dataclass
from enum import Enum


class Role(str, Enum):
    CUSTOMER = "CUSTOMER"
    ADMIN = "ADMIN"


@dataclass
class User:
    id: int | None
    email: str
    full_name: str
    hashed_password: str
    role: Role = Role.CUSTOMER
    is_active: bool = True