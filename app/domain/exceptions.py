class DomainError(Exception):
    """Base class for all business-rule errors."""


class EmailAlreadyExists(DomainError):
    pass


class InvalidCredentials(DomainError):
    pass


class NotFound(DomainError):
    pass


class PermissionDenied(DomainError):
    pass