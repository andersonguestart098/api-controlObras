from typing import Annotated, Any

from fastapi import (
    Depends,
    HTTPException,
    status,
)
from fastapi.security import (
    HTTPAuthorizationCredentials,
    HTTPBearer,
)

from app.core.security import (
    AccessTokenExpiredError,
    InvalidAccessTokenError,
    decode_access_token,
)
from app.services.auth_service import (
    AuthService,
    InvalidAccessSessionError,
    get_auth_service,
)


bearer_scheme = HTTPBearer(
    auto_error=False,
    scheme_name="BearerAuth",
    description=(
        "Informe o access token JWT recebido no login."
    ),
)


def authentication_exception(
    detail: str = "Não autenticado.",
) -> HTTPException:
    """
    Cria uma resposta HTTP padronizada para falhas
    relacionadas à autenticação.
    """

    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={
            "WWW-Authenticate": "Bearer",
        },
    )


async def get_current_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(bearer_scheme),
    ],
    auth_service: Annotated[
        AuthService,
        Depends(get_auth_service),
    ],
) -> dict[str, Any]:
    """
    Retorna o usuário autenticado.

    Etapas:

    1. Lê o header Authorization.
    2. Valida o formato Bearer.
    3. Valida assinatura e expiração do JWT.
    4. Busca o usuário no MongoDB.
    5. Confirma que o usuário está ativo.
    6. Confirma o token_version.
    """

    if credentials is None:
        raise authentication_exception(
            "Token de acesso não informado."
        )

    if credentials.scheme.lower() != "bearer":
        raise authentication_exception(
            "Esquema de autenticação inválido."
        )

    token = credentials.credentials.strip()

    if not token:
        raise authentication_exception(
            "Token de acesso não informado."
        )

    try:
        payload = decode_access_token(token)

    except AccessTokenExpiredError as exc:
        raise authentication_exception(
            "Token de acesso expirado."
        ) from exc

    except InvalidAccessTokenError as exc:
        raise authentication_exception(
            "Token de acesso inválido."
        ) from exc

    user_id = payload.get("sub")
    token_version = payload.get("ver")

    if not isinstance(user_id, str):
        raise authentication_exception(
            "Token de acesso inválido."
        )

    if not isinstance(token_version, int):
        raise authentication_exception(
            "Token de acesso inválido."
        )

    try:
        user = await auth_service.validate_access_user(
            user_id=user_id,
            token_version=token_version,
        )

    except InvalidAccessSessionError as exc:
        raise authentication_exception(
            str(exc)
        ) from exc

    return user


async def require_admin(
    current_user: Annotated[
        dict[str, Any],
        Depends(get_current_user),
    ],
) -> dict[str, Any]:
    """
    Permite acesso somente aos usuários ADMIN.
    """

    role = str(
        current_user.get("role", "")
    ).upper()

    if role != "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Você não possui permissão para "
                "acessar este recurso."
            ),
        )

    return current_user


async def require_active_user(
    current_user: Annotated[
        dict[str, Any],
        Depends(get_current_user),
    ],
) -> dict[str, Any]:
    """
    Alias explícito para rotas que exigem somente
    um usuário autenticado e ativo.

    O get_current_user já realiza essa validação.
    """

    return current_user


CurrentUser = Annotated[
    dict[str, Any],
    Depends(get_current_user),
]

AdminUser = Annotated[
    dict[str, Any],
    Depends(require_admin),
]