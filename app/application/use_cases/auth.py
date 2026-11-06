from app.application.interfaces import PasswordHasher, TokenService
from app.domain.entities import Role, User
from app.domain.exceptions import EmailAlreadyExists, InvalidCredentials
from app.domain.repositories import UserRepository


class RegisterUser:
    def __init__(self, users: UserRepository, hasher: PasswordHasher):
        self.users = users
        self.hasher = hasher

    def execute(self, email: str, full_name: str, password: str) -> User:
        email = email.lower().strip()
        if self.users.get_by_email(email):
            raise EmailAlreadyExists("Email already registered")

        user = User(
            id=None,
            email=email,
            full_name=full_name,
            hashed_password=self.hasher.hash(password),
            role=Role.CUSTOMER,  # always CUSTOMER: public users can never pick a role
        )
        return self.users.add(user)


class LoginUser:
    def __init__(self, users: UserRepository, hasher: PasswordHasher, tokens: TokenService):
        self.users = users
        self.hasher = hasher
        self.tokens = tokens

    def execute(self, email: str, password: str) -> str:
        user = self.users.get_by_email(email.lower().strip())
        if not user or not user.is_active or not self.hasher.verify(password, user.hashed_password):
            # Same message for both cases so attackers can't tell which emails exist
            raise InvalidCredentials("Incorrect email or password")
        return self.tokens.create_access_token(user.id, user.role.value)