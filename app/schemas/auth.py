from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    HttpUrl,
    SecretStr,
    field_validator,
)


class UserRole(str, Enum):
    """
    Perfis disponíveis para os usuários.
    """

    ADMIN = "ADMIN"
    USER = "USER"


def validate_password_strength(password: str) -> str:
    """
    Valida os requisitos mínimos de segurança da senha.
    """

    if len(password) < 8:
        raise ValueError(
            "A senha deve possuir pelo menos 8 caracteres."
        )

    if len(password) > 128:
        raise ValueError(
            "A senha deve possuir no máximo 128 caracteres."
        )

    if not any(character.isupper() for character in password):
        raise ValueError(
            "A senha deve possuir pelo menos uma letra maiúscula."
        )

    if not any(character.islower() for character in password):
        raise ValueError(
            "A senha deve possuir pelo menos uma letra minúscula."
        )

    if not any(character.isdigit() for character in password):
        raise ValueError(
            "A senha deve possuir pelo menos um número."
        )

    if not any(
        not character.isalnum()
        for character in password
    ):
        raise ValueError(
            "A senha deve possuir pelo menos um caractere especial."
        )

    return password


class UserCreateRequest(BaseModel):
    """
    Dados necessários para cadastrar um usuário.
    """

    name: str = Field(
        min_length=3,
        max_length=120,
        examples=["Anderson"],
    )

    email: EmailStr = Field(
        examples=["anderson@empresa.com"],
    )

    password: SecretStr = Field(
        examples=["Senha@123"],
    )

    role: UserRole = Field(
        default=UserRole.USER,
    )

    avatar_url: HttpUrl | None = Field(
        default=None,
        examples=[
            "https://res.cloudinary.com/seu-cloud/image/upload/avatar.jpg"
        ],
    )

    model_config = ConfigDict(
        str_strip_whitespace=True,
        use_enum_values=True,
    )

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized_name = " ".join(
            value.strip().split()
        )

        if len(normalized_name) < 3:
            raise ValueError(
                "O nome deve possuir pelo menos 3 caracteres."
            )

        return normalized_name

    @field_validator("email")
    @classmethod
    def normalize_email(
        cls,
        value: EmailStr,
    ) -> str:
        return str(value).strip().lower()

    @field_validator("password")
    @classmethod
    def validate_password(
        cls,
        value: SecretStr,
    ) -> SecretStr:
        validate_password_strength(
            value.get_secret_value()
        )

        return value


class LoginRequest(BaseModel):
    """
    Dados enviados no login.
    """

    email: EmailStr = Field(
        examples=["anderson@empresa.com"],
    )

    password: SecretStr = Field(
        examples=["Senha@123"],
    )

    model_config = ConfigDict(
        str_strip_whitespace=True,
    )

    @field_validator("email")
    @classmethod
    def normalize_email(
        cls,
        value: EmailStr,
    ) -> str:
        return str(value).strip().lower()


class RefreshTokenRequest(BaseModel):
    """
    Dados enviados para renovar o access token.
    """

    refresh_token: SecretStr = Field(
        min_length=20,
    )


class LogoutRequest(BaseModel):
    """
    Dados enviados para revogar uma sessão.
    """

    refresh_token: SecretStr = Field(
        min_length=20,
    )


class ForgotPasswordRequest(BaseModel):
    """
    Solicitação de recuperação de senha.
    """

    email: EmailStr = Field(
        examples=["anderson@empresa.com"],
    )

    model_config = ConfigDict(
        str_strip_whitespace=True,
    )

    @field_validator("email")
    @classmethod
    def normalize_email(
        cls,
        value: EmailStr,
    ) -> str:
        return str(value).strip().lower()


class ResetPasswordRequest(BaseModel):
    """
    Redefinição da senha usando o token recebido.
    """

    token: SecretStr = Field(
        min_length=20,
    )

    new_password: SecretStr = Field(
        examples=["NovaSenha@123"],
    )

    @field_validator("new_password")
    @classmethod
    def validate_new_password(
        cls,
        value: SecretStr,
    ) -> SecretStr:
        validate_password_strength(
            value.get_secret_value()
        )

        return value


class TokenResponse(BaseModel):
    """
    Tokens devolvidos após login ou renovação.
    """

    access_token: str
    refresh_token: str

    token_type: Literal["bearer"] = "bearer"

    expires_in: int = Field(
        description=(
            "Tempo de validade do access token em segundos."
        ),
        examples=[1800],
    )


class UserResponse(BaseModel):
    """
    Representação pública do usuário.

    Nunca retorna password_hash ou dados internos
    das sessões.
    """

    id: str

    name: str

    email: EmailStr

    role: UserRole

    avatar_url: str | None = None

    is_active: bool

    created_at: datetime

    updated_at: datetime | None = None

    last_login_at: datetime | None = None

    model_config = ConfigDict(
        from_attributes=True,
        use_enum_values=True,
    )


class LoginResponse(TokenResponse):
    """
    Resposta completa do login.
    """

    user: UserResponse


class RefreshResponse(TokenResponse):
    """
    Resposta da renovação dos tokens.
    """

    pass


class MessageResponse(BaseModel):
    """
    Resposta genérica para operações sem retorno de dados.
    """

    message: str


class ForgotPasswordResponse(MessageResponse):
    """
    Resposta genérica da recuperação de senha.

    Não revela se o e-mail existe no banco.
    """

    pass