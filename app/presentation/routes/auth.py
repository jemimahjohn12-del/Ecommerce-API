from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from app.application.use_cases.auth import LoginUser, RegisterUser
from app.domain.entities import User
from app.domain.exceptions import EmailAlreadyExists, InvalidCredentials
from app.presentation.dependencies import (
    get_current_user, get_hasher, get_token_service, get_user_repo,
)
from app.presentation.schemas import RegisterRequest, TokenResponse, UserResponse

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(data: RegisterRequest, users=Depends(get_user_repo), hasher=Depends(get_hasher)):
    try:
        return RegisterUser(users, hasher).execute(data.email, data.full_name, data.password)
    except EmailAlreadyExists as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.post("/login", response_model=TokenResponse)
def login(
    form: OAuth2PasswordRequestForm = Depends(),
    users=Depends(get_user_repo),
    hasher=Depends(get_hasher),
    tokens=Depends(get_token_service),
):
    # OAuth2 forms call the email field "username"
    try:
        token = LoginUser(users, hasher, tokens).execute(form.username, form.password)
    except InvalidCredentials as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserResponse)
def me(current_user: User = Depends(get_current_user)):
    return current_user