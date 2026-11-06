from abc import ABC, abstractmethod


class PasswordHasher(ABC):
    @abstractmethod
    def hash(self, password: str) -> str: ...

    @abstractmethod
    def verify(self, password: str, hashed: str) -> bool: ...


class TokenService(ABC):
    @abstractmethod
    def create_access_token(self, user_id: int, role: str) -> str: ...

    @abstractmethod
    def decode_token(self, token: str) -> int:
        """Return the user id or raise InvalidCredentials."""