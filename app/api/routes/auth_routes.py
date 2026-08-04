from typing import Any

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    status,
)

from app.api.dependencies import (
    AdminUser,
    CurrentUser,
)
from app.repositories.user_repository import (
    UserAlreadyExistsError,
)
from app.schemas.auth import (
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    LoginRequest,
    LoginResponse,
    LogoutRequest,
    MessageResponse,
    RefreshResponse,
    RefreshTokenRequest,
    ResetPasswordRequest,
    UserCreateRequest,
    UserResponse,
)
from app.services.auth_service import (
    AuthService,
    AuthServiceError,
    InvalidCredentialsError,
    InvalidPasswordResetTokenError,
    InvalidRefreshTokenError,
    PasswordResetEmailError,
    RefreshTokenReuseError,
    UserInactiveError,
    UserNotFoundError,
    get_auth_service,
)


router = APIRouter(
    prefix="/auth",
    tags=["Autenticação"],
)


def get_client_metadata(
    request: Request,
) -> tuple[str | None, str | None]:
    """
    Obtém dados básicos da requisição para auditoria
    das sessões e recuperações de senha.
    """

    ip_address = (
        request.client.host
        if request.client is not None
        else None
    )

    user_agent = request.headers.get(
        "user-agent"
    )

    # Evita armazenar um User-Agent excessivamente grande.
    if user_agent:
        user_agent = user_agent[:500]

    return ip_address, user_agent


# =========================================================
# USUÁRIOS
# =========================================================


@router.post(
    "/users",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Cadastrar usuário",
)
async def create_user(
    payload: UserCreateRequest,
    _: AdminUser,
    auth_service: AuthService = Depends(
        get_auth_service
    ),
) -> UserResponse:
    """
    Cadastra um novo usuário.

    Apenas usuários com perfil ADMIN podem acessar.
    """

    try:
        return await auth_service.create_user(
            payload
        )

    except UserAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


# =========================================================
# LOGIN
# =========================================================


@router.post(
    "/login",
    response_model=LoginResponse,
    summary="Realizar login",
)
async def login(
    payload: LoginRequest,
    request: Request,
    auth_service: AuthService = Depends(
        get_auth_service
    ),
) -> LoginResponse:
    """
    Autentica o usuário usando e-mail e senha.

    Retorna:

    - access token JWT;
    - refresh token;
    - dados públicos do usuário.
    """

    ip_address, user_agent = get_client_metadata(
        request
    )

    try:
        return await auth_service.login(
            payload,
            ip_address=ip_address,
            user_agent=user_agent,
        )

    except InvalidCredentialsError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={
                "WWW-Authenticate": "Bearer",
            },
        ) from exc

    except UserInactiveError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc


# =========================================================
# USUÁRIO AUTENTICADO
# =========================================================


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Consultar usuário autenticado",
)
async def get_me(
    current_user: CurrentUser,
    auth_service: AuthService = Depends(
        get_auth_service
    ),
) -> UserResponse:
    """
    Retorna os dados do usuário dono do access token.
    """

    try:
        return await auth_service.get_user_by_id(
            str(current_user["_id"])
        )

    except UserNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sessão de acesso inválida.",
            headers={
                "WWW-Authenticate": "Bearer",
            },
        ) from exc


# =========================================================
# REFRESH TOKEN
# =========================================================


@router.post(
    "/refresh",
    response_model=RefreshResponse,
    summary="Renovar tokens",
)
async def refresh_tokens(
    payload: RefreshTokenRequest,
    request: Request,
    auth_service: AuthService = Depends(
        get_auth_service
    ),
) -> RefreshResponse:
    """
    Renova o access token e rotaciona o refresh token.

    O refresh token enviado deixa de ser válido e deve
    ser substituído pelo novo token retornado.
    """

    ip_address, user_agent = get_client_metadata(
        request
    )

    try:
        return await auth_service.refresh(
            payload,
            ip_address=ip_address,
            user_agent=user_agent,
        )

    except RefreshTokenReuseError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={
                "WWW-Authenticate": "Bearer",
            },
        ) from exc

    except InvalidRefreshTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={
                "WWW-Authenticate": "Bearer",
            },
        ) from exc

    except UserInactiveError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc


# =========================================================
# LOGOUT
# =========================================================


@router.post(
    "/logout",
    response_model=MessageResponse,
    summary="Encerrar sessão atual",
)
async def logout(
    payload: LogoutRequest,
    auth_service: AuthService = Depends(
        get_auth_service
    ),
) -> MessageResponse:
    """
    Revoga o refresh token informado.

    A rota não exige access token porque ele pode já
    ter expirado no momento do logout.
    """

    return await auth_service.logout(
        payload
    )


@router.post(
    "/logout-all",
    response_model=MessageResponse,
    summary="Encerrar todas as sessões",
)
async def logout_all(
    current_user: CurrentUser,
    auth_service: AuthService = Depends(
        get_auth_service
    ),
) -> MessageResponse:
    """
    Revoga todos os refresh tokens e invalida todos
    os access tokens do usuário.
    """

    try:
        return await auth_service.logout_all(
            str(current_user["_id"])
        )

    except UserNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


# =========================================================
# RECUPERAÇÃO DE SENHA
# =========================================================


@router.post(
    "/forgot-password",
    response_model=ForgotPasswordResponse,
    summary="Solicitar recuperação de senha",
)
async def forgot_password(
    payload: ForgotPasswordRequest,
    request: Request,
    auth_service: AuthService = Depends(
        get_auth_service
    ),
) -> ForgotPasswordResponse:
    """
    Solicita um link para redefinição de senha.

    A resposta é sempre genérica para não revelar
    se determinado e-mail está cadastrado.
    """

    ip_address, user_agent = get_client_metadata(
        request
    )

    try:
        return await auth_service.forgot_password(
            email=str(payload.email),
            ip_address=ip_address,
            user_agent=user_agent,
        )

    except PasswordResetEmailError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc


@router.post(
    "/reset-password",
    response_model=MessageResponse,
    summary="Redefinir senha",
)
async def reset_password(
    payload: ResetPasswordRequest,
    auth_service: AuthService = Depends(
        get_auth_service
    ),
) -> MessageResponse:
    """
    Redefine a senha usando um token válido e de uso único.

    Depois da alteração, todas as sessões anteriores
    são revogadas.
    """

    try:
        return await auth_service.reset_password(
            payload
        )

    except InvalidPasswordResetTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    except UserInactiveError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc

    except AuthServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc