from typing import Any

from app.core.security import (
    create_access_token,
    generate_password_reset_token,
    generate_refresh_token,
    get_access_token_expires_in_seconds,
    get_password_reset_expiration,
    get_refresh_token_expiration,
    hash_opaque_token,
    hash_password,
    utc_now,
    verify_and_update_password,
)
from app.repositories.password_reset_repository import (
    PasswordResetRepository,
    get_password_reset_repository,
)
from app.repositories.refresh_session_repository import (
    RefreshSessionRepository,
    get_refresh_session_repository,
)
from app.repositories.user_repository import (
    UserAlreadyExistsError,
    UserRepository,
    get_user_repository,
)
from app.schemas.auth import (
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
from app.services.email_service import (
    EmailDeliveryError,
    EmailService,
    get_email_service,
)


# =========================================================
# EXCEÇÕES DO SERVIÇO
# =========================================================


class AuthServiceError(Exception):
    """
    Exceção base do serviço de autenticação.
    """

    pass


class InvalidCredentialsError(AuthServiceError):
    """
    E-mail ou senha inválidos.
    """

    pass


class UserInactiveError(AuthServiceError):
    """
    Usuário encontrado, mas desativado.
    """

    pass


class UserNotFoundError(AuthServiceError):
    """
    Usuário não encontrado.
    """

    pass


class InvalidRefreshTokenError(AuthServiceError):
    """
    Refresh token inválido, expirado ou revogado.
    """

    pass


class RefreshTokenReuseError(AuthServiceError):
    """
    Refresh token antigo foi reutilizado após rotação.
    """

    pass


class InvalidPasswordResetTokenError(AuthServiceError):
    """
    Token de recuperação inválido ou expirado.
    """

    pass


class PasswordResetEmailError(AuthServiceError):
    """
    Não foi possível disponibilizar o e-mail de recuperação.
    """

    pass


class InvalidAccessSessionError(AuthServiceError):
    """
    O usuário ou a sessão indicada pelo access token
    não é mais válida.
    """

    pass


# =========================================================
# SERVIÇO
# =========================================================


class AuthService:
    """
    Serviço principal da autenticação.

    Responsabilidades:

    - criar usuários;
    - autenticar usuário;
    - gerar access e refresh tokens;
    - rotacionar refresh tokens;
    - realizar logout;
    - solicitar recuperação de senha;
    - redefinir senha;
    - validar usuário de um access token.
    """

    def __init__(
        self,
        user_repository: UserRepository,
        refresh_session_repository: RefreshSessionRepository,
        password_reset_repository: PasswordResetRepository,
        email_service: EmailService,
    ) -> None:
        self.user_repository = user_repository
        self.refresh_session_repository = (
            refresh_session_repository
        )
        self.password_reset_repository = (
            password_reset_repository
        )
        self.email_service = email_service

    # =====================================================
    # USUÁRIO
    # =====================================================

    async def create_user(
        self,
        request: UserCreateRequest,
    ) -> UserResponse:
        """
        Cadastra um usuário.

        A autorização para criar usuários será aplicada
        posteriormente na rota, permitindo apenas ADMIN.
        """

        password = request.password.get_secret_value()

        password_hash = hash_password(password)

        role = (
            request.role.value
            if hasattr(request.role, "value")
            else str(request.role)
        )

        user = await self.user_repository.create(
            name=request.name,
            email=str(request.email),
            password_hash=password_hash,
            role=role,
            is_active=True,
            avatar_url=(
                str(request.avatar_url)
                if request.avatar_url is not None
                else None
            ),
        )

        return self._to_user_response(user)

    async def get_user_by_id(
        self,
        user_id: str,
    ) -> UserResponse:
        """
        Busca a representação pública de um usuário.
        """

        user = await self.user_repository.find_by_id(
            user_id
        )

        if user is None:
            raise UserNotFoundError(
                "Usuário não encontrado."
            )

        return self._to_user_response(user)

    async def validate_access_user(
        self,
        *,
        user_id: str,
        token_version: int,
    ) -> dict[str, Any]:
        """
        Valida o usuário indicado pelo access token.

        Além da assinatura e expiração do JWT, a aplicação
        precisa validar:

        - se o usuário ainda existe;
        - se está ativo;
        - se token_version ainda corresponde ao token.
        """

        user = await self.user_repository.find_by_id(
            user_id
        )

        if user is None:
            raise InvalidAccessSessionError(
                "Sessão de acesso inválida."
            )

        if not user.get("is_active", False):
            raise InvalidAccessSessionError(
                "Usuário desativado."
            )

        current_token_version = int(
            user.get("token_version", 0)
        )

        if current_token_version != token_version:
            raise InvalidAccessSessionError(
                "Sessão de acesso revogada."
            )

        return user

    # =====================================================
    # LOGIN
    # =====================================================

    async def login(
        self,
        request: LoginRequest,
        *,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> LoginResponse:
        """
        Autentica o usuário e cria uma sessão.
        """

        user = await self.user_repository.find_by_email(
            str(request.email)
        )

        # A mensagem é propositalmente genérica para não
        # revelar se o e-mail está cadastrado.
        if user is None:
            raise InvalidCredentialsError(
                "E-mail ou senha inválidos."
            )

        password = request.password.get_secret_value()

        password_valid, updated_hash = (
            verify_and_update_password(
                password,
                user.get("password_hash", ""),
            )
        )

        if not password_valid:
            raise InvalidCredentialsError(
                "E-mail ou senha inválidos."
            )

        if not user.get("is_active", False):
            raise UserInactiveError(
                "Usuário desativado."
            )

        # O pwdlib pode recomendar atualizar o hash quando
        # os parâmetros do algoritmo forem modernizados.
        if updated_hash is not None:
            await self.user_repository.update_password_hash_only(
                user_id=user["_id"],
                password_hash=updated_hash,
            )

            user["password_hash"] = updated_hash

        updated_user = (
            await self.user_repository.update_last_login(
                user["_id"]
            )
        )

        if updated_user is not None:
            user = updated_user

        access_token = self._create_user_access_token(
            user
        )

        refresh_token = generate_refresh_token()
        refresh_token_hash = hash_opaque_token(
            refresh_token
        )

        await self.refresh_session_repository.create(
            user_id=user["_id"],
            token_hash=refresh_token_hash,
            expires_at=get_refresh_token_expiration(),
            ip_address=ip_address,
            user_agent=user_agent,
        )

        return LoginResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=(
                get_access_token_expires_in_seconds()
            ),
            user=self._to_user_response(user),
        )

    # =====================================================
    # REFRESH TOKEN
    # =====================================================

    async def refresh(
        self,
        request: RefreshTokenRequest,
        *,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> RefreshResponse:
        """
        Rotaciona o refresh token.

        O token antigo é revogado e um novo é criado.
        """

        current_token = (
            request.refresh_token.get_secret_value()
        )

        current_token_hash = hash_opaque_token(
            current_token
        )

        current_session = (
            await self.refresh_session_repository
            .find_by_token_hash(
                current_token_hash
            )
        )

        if current_session is None:
            raise InvalidRefreshTokenError(
                "Refresh token inválido."
            )

        if current_session.get("revoked_at") is not None:
            await self._handle_revoked_refresh_session(
                current_session
            )

        expires_at = current_session.get(
            "expires_at"
        )

        if (
            expires_at is None
            or expires_at <= utc_now()
        ):
            raise InvalidRefreshTokenError(
                "Refresh token expirado."
            )

        user = await self.user_repository.find_by_id(
            current_session["user_id"]
        )

        if user is None:
            raise InvalidRefreshTokenError(
                "Usuário da sessão não encontrado."
            )

        if not user.get("is_active", False):
            await (
                self.refresh_session_repository
                .revoke_all_by_user(
                    user_id=user["_id"],
                    reason="USER_INACTIVE",
                )
            )

            raise UserInactiveError(
                "Usuário desativado."
            )

        new_refresh_token = generate_refresh_token()

        new_refresh_token_hash = hash_opaque_token(
            new_refresh_token
        )

        # Consome atomicamente o token antigo.
        consumed_session = (
            await self.refresh_session_repository
            .consume_for_rotation(
                token_hash=current_token_hash,
                replaced_by_token_hash=(
                    new_refresh_token_hash
                ),
            )
        )

        # Outra requisição pode ter utilizado o mesmo token
        # entre a leitura e o consumo.
        if consumed_session is None:
            latest_session = (
                await self.refresh_session_repository
                .find_by_token_hash(
                    current_token_hash
                )
            )

            if latest_session is not None:
                await self._handle_revoked_refresh_session(
                    latest_session
                )

            raise InvalidRefreshTokenError(
                "Refresh token inválido ou já utilizado."
            )

        await self.refresh_session_repository.create(
            user_id=user["_id"],
            token_hash=new_refresh_token_hash,
            expires_at=get_refresh_token_expiration(),
            family_id=consumed_session["family_id"],
            ip_address=ip_address,
            user_agent=user_agent,
        )

        access_token = self._create_user_access_token(
            user
        )

        return RefreshResponse(
            access_token=access_token,
            refresh_token=new_refresh_token,
            expires_in=(
                get_access_token_expires_in_seconds()
            ),
        )

    async def _handle_revoked_refresh_session(
        self,
        session: dict[str, Any],
    ) -> None:
        """
        Trata refresh tokens que já foram revogados.

        Quando o token foi revogado porque já passou por
        rotação, sua reutilização pode indicar roubo.
        """

        revoke_reason = session.get(
            "revoke_reason"
        )

        if revoke_reason == "TOKEN_ROTATED":
            family_id = session.get("family_id")

            if family_id:
                await (
                    self.refresh_session_repository
                    .revoke_family(
                        family_id=family_id,
                        reason=(
                            "TOKEN_REUSE_DETECTED"
                        ),
                    )
                )

            # Invalida também os access tokens do usuário.
            await self.user_repository.increment_token_version(
                session["user_id"]
            )

            raise RefreshTokenReuseError(
                "Reutilização de refresh token detectada. "
                "A sessão foi encerrada por segurança."
            )

        raise InvalidRefreshTokenError(
            "Refresh token revogado."
        )

    # =====================================================
    # LOGOUT
    # =====================================================

    async def logout(
        self,
        request: LogoutRequest,
    ) -> MessageResponse:
        """
        Revoga o refresh token informado.

        A resposta permanece positiva mesmo quando o token
        já estiver revogado ou não existir.
        """

        refresh_token = (
            request.refresh_token.get_secret_value()
        )

        token_hash = hash_opaque_token(
            refresh_token
        )

        await (
            self.refresh_session_repository
            .revoke_by_token_hash(
                token_hash=token_hash,
                reason="LOGOUT",
            )
        )

        return MessageResponse(
            message="Logout realizado com sucesso."
        )

    async def logout_all(
        self,
        user_id: str,
    ) -> MessageResponse:
        """
        Encerra todas as sessões do usuário.

        Também incrementa token_version para invalidar
        os access tokens ainda não expirados.
        """

        user = await self.user_repository.find_by_id(
            user_id
        )

        if user is None:
            raise UserNotFoundError(
                "Usuário não encontrado."
            )

        await (
            self.refresh_session_repository
            .revoke_all_by_user(
                user_id=user["_id"],
                reason="LOGOUT_ALL",
            )
        )

        await self.user_repository.increment_token_version(
            user["_id"]
        )

        return MessageResponse(
            message=(
                "Todas as sessões foram encerradas."
            )
        )

    # =====================================================
    # RECUPERAÇÃO DE SENHA
    # =====================================================

    async def forgot_password(
        self,
        email: str,
        *,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> ForgotPasswordResponse:
        """
        Cria e envia um token de recuperação.

        A resposta é sempre a mesma, exista ou não usuário,
        evitando enumeração de contas.
        """

        generic_response = ForgotPasswordResponse(
            message=(
                "Se o e-mail estiver cadastrado, "
                "você receberá as instruções "
                "para redefinir a senha."
            )
        )

        user = await self.user_repository.find_by_email(
            email
        )

        if user is None:
            return generic_response

        if not user.get("is_active", False):
            return generic_response

        reset_token = generate_password_reset_token()

        reset_token_hash = hash_opaque_token(
            reset_token
        )

        await self.password_reset_repository.create(
            user_id=user["_id"],
            token_hash=reset_token_hash,
            expires_at=(
                get_password_reset_expiration()
            ),
            ip_address=ip_address,
            user_agent=user_agent,
        )

        try:
            await self.email_service.send_password_reset_email(
                recipient_email=user["email"],
                recipient_name=user["name"],
                token=reset_token,
            )

        except EmailDeliveryError as exc:
            await (
                self.password_reset_repository
                .invalidate_by_token_hash(
                    token_hash=reset_token_hash,
                    reason="EMAIL_DELIVERY_FAILED",
                )
            )

            raise PasswordResetEmailError(
                "Não foi possível enviar o e-mail "
                "de recuperação."
            ) from exc

        return generic_response

    async def reset_password(
        self,
        request: ResetPasswordRequest,
    ) -> MessageResponse:
        """
        Redefine a senha usando um token de uso único.
        """

        reset_token = (
            request.token.get_secret_value()
        )

        token_hash = hash_opaque_token(
            reset_token
        )

        # O consumo é atômico e impede que o mesmo link
        # seja utilizado simultaneamente duas vezes.
        reset_session = (
            await self.password_reset_repository.consume(
                token_hash
            )
        )

        if reset_session is None:
            raise InvalidPasswordResetTokenError(
                "Token de recuperação inválido "
                "ou expirado."
            )

        user = await self.user_repository.find_by_id(
            reset_session["user_id"]
        )

        if user is None:
            raise InvalidPasswordResetTokenError(
                "Usuário da recuperação não encontrado."
            )

        if not user.get("is_active", False):
            raise UserInactiveError(
                "Usuário desativado."
            )

        new_password = (
            request.new_password.get_secret_value()
        )

        # Impede que o usuário redefina para a mesma senha.
        same_password, _ = verify_and_update_password(
            new_password,
            user.get("password_hash", ""),
        )

        if same_password:
            raise AuthServiceError(
                "A nova senha deve ser diferente "
                "da senha atual."
            )

        new_password_hash = hash_password(
            new_password
        )

        updated_user = (
            await self.user_repository.update_password(
                user_id=user["_id"],
                password_hash=new_password_hash,
            )
        )

        if updated_user is None:
            raise UserNotFoundError(
                "Não foi possível atualizar o usuário."
            )

        # Encerra todas as sessões existentes.
        await (
            self.refresh_session_repository
            .revoke_all_by_user(
                user_id=user["_id"],
                reason="PASSWORD_CHANGED",
            )
        )

        # Invalida outros links de recuperação.
        await (
            self.password_reset_repository
            .invalidate_all_by_user(
                user_id=user["_id"],
                reason="PASSWORD_CHANGED",
            )
        )

        return MessageResponse(
            message=(
                "Senha redefinida com sucesso. "
                "Faça login novamente."
            )
        )

    # =====================================================
    # CONVERSÕES
    # =====================================================

    def _create_user_access_token(
        self,
        user: dict[str, Any],
    ) -> str:
        """
        Gera um JWT a partir do documento do usuário.
        """

        return create_access_token(
            user_id=str(user["_id"]),
            email=user["email"],
            role=user["role"],
            token_version=int(
                user.get("token_version", 0)
            ),
        )

    @staticmethod
    def _to_user_response(
            user: dict[str, Any],
    ) -> UserResponse:
        return UserResponse(
            id=str(user["_id"]),
            name=user["name"],
            email=user["email"],
            role=user["role"],
            is_active=user.get(
                "is_active",
                False,
            ),
            avatar_url=user.get(
                "avatar_url"
            ),
            created_at=user["created_at"],
            updated_at=user.get("updated_at"),
            last_login_at=user.get(
                "last_login_at"
            ),
        )


def get_auth_service() -> AuthService:
    """
    Cria uma instância do AuthService com todas
    as dependências necessárias.
    """

    return AuthService(
        user_repository=get_user_repository(),
        refresh_session_repository=(
            get_refresh_session_repository()
        ),
        password_reset_repository=(
            get_password_reset_repository()
        ),
        email_service=get_email_service(),
    )