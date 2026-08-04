import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

import jwt
from fastapi import Header, HTTPException, status
from jwt.exceptions import (
    ExpiredSignatureError,
    InvalidTokenError,
)
from pwdlib import PasswordHash

from app.core.config import get_settings


# PasswordHash.recommended() utiliza um algoritmo seguro
# recomendado pela biblioteca. Atualmente, Argon2.
password_hasher = PasswordHash.recommended()


class AccessTokenError(Exception):
    """
    Exceção base para erros de access token.
    """

    pass


class AccessTokenExpiredError(AccessTokenError):
    """
    Exceção lançada quando o access token expirou.
    """

    pass


class InvalidAccessTokenError(AccessTokenError):
    """
    Exceção lançada quando o access token é inválido.
    """

    pass


def utc_now() -> datetime:
    """
    Retorna a data e hora atual em UTC com timezone.

    Todas as datas de segurança devem ser armazenadas
    no MongoDB em UTC.
    """

    return datetime.now(timezone.utc)


# =========================================================
# API KEY
# =========================================================


async def validar_api_key(
    x_api_key: str | None = Header(
        default=None,
        alias="X-API-Key",
    ),
) -> None:
    """
    Valida a API key usada nas integrações internas.

    Essa função foi mantida para não quebrar as rotas
    atuais do projeto.
    """

    settings = get_settings()

    if x_api_key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key não informada.",
            headers={
                "WWW-Authenticate": "ApiKey",
            },
        )

    api_key_valida = secrets.compare_digest(
        x_api_key,
        settings.api_key,
    )

    if not api_key_valida:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key inválida.",
            headers={
                "WWW-Authenticate": "ApiKey",
            },
        )


# =========================================================
# SENHAS
# =========================================================


def hash_password(password: str) -> str:
    """
    Gera um hash seguro para a senha.

    A senha original nunca deve ser armazenada no MongoDB.
    """

    if not password:
        raise ValueError(
            "A senha não pode ser vazia."
        )

    return password_hasher.hash(password)


def verify_password(
    password: str,
    password_hash: str,
) -> bool:
    """
    Verifica se a senha informada corresponde ao hash.
    """

    if not password or not password_hash:
        return False

    try:
        return password_hasher.verify(
            password,
            password_hash,
        )
    except Exception:
        # Um hash inválido ou corrompido não deve derrubar
        # a requisição de login.
        return False


def verify_and_update_password(
    password: str,
    password_hash: str,
) -> tuple[bool, str | None]:
    """
    Verifica a senha e informa se o hash precisa ser atualizado.

    Retorno:

    (
        senha_valida,
        novo_hash_ou_none
    )

    Isso permite atualizar automaticamente hashes antigos
    caso o algoritmo ou os parâmetros sejam alterados no futuro.
    """

    if not password or not password_hash:
        return False, None

    try:
        return password_hasher.verify_and_update(
            password,
            password_hash,
        )
    except Exception:
        return False, None


# =========================================================
# ACCESS TOKEN JWT
# =========================================================


def create_access_token(
    *,
    user_id: str,
    email: str,
    role: str,
    token_version: int = 0,
) -> str:
    """
    Cria um access token JWT.

    Parâmetros:
        user_id:
            ID do usuário no MongoDB.

        email:
            E-mail do usuário.

        role:
            Papel do usuário, por exemplo USER ou ADMIN.

        token_version:
            Número utilizado para invalidar access tokens
            antigos após troca de senha ou revogação geral.
    """

    settings = get_settings()

    issued_at = utc_now()

    expires_at = issued_at + timedelta(
        minutes=settings.jwt_access_token_minutes
    )

    payload: dict[str, Any] = {
        # Identificador do usuário.
        "sub": str(user_id),

        # Dados auxiliares.
        "email": email,
        "role": role,

        # Versão de segurança do usuário.
        "ver": int(token_version),

        # Impede que outro tipo de token seja aceito
        # como access token.
        "type": "access",

        # Identificador único do JWT.
        "jti": str(uuid4()),

        # Data de emissão.
        "iat": issued_at,

        # Data de expiração.
        "exp": expires_at,
    }

    return jwt.encode(
        payload=payload,
        key=settings.jwt_secret_key.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )


def decode_access_token(
    token: str,
) -> dict[str, Any]:
    """
    Valida e decodifica um access token JWT.

    Retorna o payload quando o token for válido.
    """

    settings = get_settings()

    if not token:
        raise InvalidAccessTokenError(
            "Token de acesso não informado."
        )

    try:
        payload: dict[str, Any] = jwt.decode(
            jwt=token,
            key=settings.jwt_secret_key.get_secret_value(),
            algorithms=[
                settings.jwt_algorithm,
            ],
            options={
                "require": [
                    "sub",
                    "exp",
                    "iat",
                    "type",
                    "ver",
                    "jti",
                ],
            },
        )

    except ExpiredSignatureError as exc:
        raise AccessTokenExpiredError(
            "Token de acesso expirado."
        ) from exc

    except InvalidTokenError as exc:
        raise InvalidAccessTokenError(
            "Token de acesso inválido."
        ) from exc

    if payload.get("type") != "access":
        raise InvalidAccessTokenError(
            "Tipo de token inválido."
        )

    user_id = payload.get("sub")

    if not isinstance(user_id, str) or not user_id.strip():
        raise InvalidAccessTokenError(
            "Identificador do usuário inválido."
        )

    token_version = payload.get("ver")

    if not isinstance(token_version, int):
        raise InvalidAccessTokenError(
            "Versão do token inválida."
        )

    role = payload.get("role")

    if not isinstance(role, str) or not role.strip():
        raise InvalidAccessTokenError(
            "Perfil do usuário inválido."
        )

    return payload


def get_access_token_expires_in_seconds() -> int:
    """
    Retorna a duração do access token em segundos.

    Exemplo:
        30 minutos = 1800 segundos.
    """

    settings = get_settings()

    return settings.jwt_access_token_seconds


# =========================================================
# REFRESH TOKEN
# =========================================================


def generate_refresh_token() -> str:
    """
    Gera um refresh token aleatório.

    O refresh token não será JWT. Ele será uma sequência
    criptograficamente aleatória.
    """

    return secrets.token_urlsafe(48)


def get_refresh_token_expiration() -> datetime:
    """
    Retorna a data de expiração de um refresh token.
    """

    settings = get_settings()

    return utc_now() + timedelta(
        days=settings.jwt_refresh_token_days
    )


# =========================================================
# RECUPERAÇÃO DE SENHA
# =========================================================


def generate_password_reset_token() -> str:
    """
    Gera um token aleatório para recuperação de senha.
    """

    return secrets.token_urlsafe(48)


def get_password_reset_expiration() -> datetime:
    """
    Retorna a data de expiração do token de recuperação.
    """

    settings = get_settings()

    return utc_now() + timedelta(
        minutes=settings.password_reset_token_minutes
    )


# =========================================================
# HASH DOS TOKENS
# =========================================================


def hash_opaque_token(token: str) -> str:
    """
    Gera o SHA-256 de um refresh token ou token
    de recuperação.

    O usuário recebe o token original, mas o MongoDB
    armazena somente o hash.
    """

    if not token:
        raise ValueError(
            "O token não pode ser vazio."
        )

    return hashlib.sha256(
        token.encode("utf-8")
    ).hexdigest()