from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.application.interfaces import PasswordHasher, TokenService
from app.core.config import settings
from app.domain.exceptions import InvalidCredentials


class BcryptPasswordHasher(PasswordHasher):
    def hash(self, password: str) -> str:
        return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    def verify(self, password: str, hashed: str) -> bool:
        return bcrypt.checkpw(password.encode(), hashed.encode())


class JWTTokenService(TokenService):
    def create_access_token(self, user_id: int, role: str) -> str:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
        payload = {"sub": str(user_id), "role": role, "exp": expire}
        return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)

    def decode_token(self, token: str) -> int:
        try:
            payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
            return int(payload["sub"])
        except jwt.ExpiredSignatureError:
            raise InvalidCredentials("Token has expired")
        except (jwt.InvalidTokenError, KeyError, ValueError):
            raise InvalidCredentials("Invalid token")