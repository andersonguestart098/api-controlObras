from datetime import datetime
from typing import Any
from uuid import uuid4

from bson import ObjectId
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from app.core.database import get_database
from app.core.security import utc_now


class RefreshSessionAlreadyExistsError(Exception):
    """
    Erro extremamente raro, lançado caso o hash de um
    refresh token já exista no banco.
    """

    pass


class InvalidRefreshUserIdError(Exception):
    """
    Erro lançado quando o ID do usuário não é um
    ObjectId válido.
    """

    pass


def parse_user_object_id(
    user_id: str | ObjectId,
) -> ObjectId:
    """
    Converte o ID do usuário para ObjectId.
    """

    if isinstance(user_id, ObjectId):
        return user_id

    if not ObjectId.is_valid(user_id):
        raise InvalidRefreshUserIdError(
            "ID do usuário inválido."
        )

    return ObjectId(user_id)


class RefreshSessionRepository:
    """
    Responsável pelo acesso à coleção refresh_sessions.

    O refresh token original nunca será salvo no MongoDB.
    Somente o hash SHA-256 será armazenado.
    """

    @property
    def collection(self) -> Any:
        """
        Retorna a coleção refresh_sessions.
        """

        database = get_database()

        return database["refresh_sessions"]

    async def create(
        self,
        *,
        user_id: str | ObjectId,
        token_hash: str,
        expires_at: datetime,
        family_id: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> dict[str, Any]:
        """
        Cria uma nova sessão de refresh token.

        family_id identifica todos os tokens originados da
        mesma sessão de login.

        Exemplo:

            login
              └── refresh A
                    └── refresh B
                          └── refresh C

        Todos possuirão o mesmo family_id.
        """

        object_id = parse_user_object_id(
            user_id
        )

        now = utc_now()

        session_document: dict[str, Any] = {
            "user_id": object_id,
            "token_hash": token_hash,
            "family_id": family_id or str(uuid4()),

            "created_at": now,
            "expires_at": expires_at,
            "last_used_at": None,

            "revoked_at": None,
            "revoke_reason": None,

            # Preenchido quando o refresh token for
            # substituído durante a rotação.
            "replaced_by_token_hash": None,

            # Informações opcionais para auditoria.
            "ip_address": ip_address,
            "user_agent": user_agent,
        }

        try:
            result = await self.collection.insert_one(
                session_document
            )

        except DuplicateKeyError as exc:
            raise RefreshSessionAlreadyExistsError(
                "Já existe uma sessão com esse token."
            ) from exc

        session_document["_id"] = result.inserted_id

        return session_document

    async def find_by_token_hash(
        self,
        token_hash: str,
    ) -> dict[str, Any] | None:
        """
        Localiza uma sessão pelo hash do refresh token.

        Retorna sessões ativas, expiradas ou revogadas.
        Isso será útil para detectar reutilização de tokens.
        """

        return await self.collection.find_one(
            {
                "token_hash": token_hash,
            }
        )

    async def find_active_by_token_hash(
        self,
        token_hash: str,
    ) -> dict[str, Any] | None:
        """
        Localiza uma sessão somente quando ela estiver:

        - não revogada;
        - ainda dentro da validade.
        """

        return await self.collection.find_one(
            {
                "token_hash": token_hash,
                "revoked_at": None,
                "expires_at": {
                    "$gt": utc_now(),
                },
            }
        )

    async def consume_for_rotation(
        self,
        *,
        token_hash: str,
        replaced_by_token_hash: str,
    ) -> dict[str, Any] | None:
        """
        Consome atomicamente um refresh token durante a rotação.

        O filtro garante que duas requisições simultâneas não
        consigam utilizar o mesmo refresh token.

        Quando consumido:

        - revoked_at recebe a data atual;
        - revoke_reason recebe TOKEN_ROTATED;
        - replaced_by_token_hash aponta para o novo token;
        - last_used_at registra o uso.
        """

        now = utc_now()

        return await self.collection.find_one_and_update(
            {
                "token_hash": token_hash,
                "revoked_at": None,
                "expires_at": {
                    "$gt": now,
                },
            },
            {
                "$set": {
                    "last_used_at": now,
                    "revoked_at": now,
                    "revoke_reason": "TOKEN_ROTATED",
                    "replaced_by_token_hash": (
                        replaced_by_token_hash
                    ),
                }
            },
            return_document=ReturnDocument.AFTER,
        )

    async def revoke_by_token_hash(
        self,
        *,
        token_hash: str,
        reason: str = "LOGOUT",
    ) -> dict[str, Any] | None:
        """
        Revoga uma sessão específica.

        Utilizado principalmente no logout.
        """

        now = utc_now()

        return await self.collection.find_one_and_update(
            {
                "token_hash": token_hash,
                "revoked_at": None,
            },
            {
                "$set": {
                    "revoked_at": now,
                    "revoke_reason": reason,
                    "last_used_at": now,
                }
            },
            return_document=ReturnDocument.AFTER,
        )

    async def revoke_family(
        self,
        *,
        family_id: str,
        reason: str = "TOKEN_REUSE_DETECTED",
    ) -> int:
        """
        Revoga todas as sessões pertencentes à mesma família.

        Será utilizado quando um refresh token antigo e já
        consumido for reutilizado. Isso pode indicar que o token
        foi copiado ou roubado.
        """

        now = utc_now()

        result = await self.collection.update_many(
            {
                "family_id": family_id,
                "revoked_at": None,
            },
            {
                "$set": {
                    "revoked_at": now,
                    "revoke_reason": reason,
                }
            },
        )

        return result.modified_count

    async def revoke_all_by_user(
        self,
        *,
        user_id: str | ObjectId,
        reason: str = "ALL_SESSIONS_REVOKED",
    ) -> int:
        """
        Revoga todas as sessões ativas de um usuário.

        Será utilizado em situações como:

        - troca de senha;
        - usuário desativado;
        - logout de todos os dispositivos;
        - suspeita de comprometimento.
        """

        try:
            object_id = parse_user_object_id(
                user_id
            )

        except InvalidRefreshUserIdError:
            return 0

        now = utc_now()

        result = await self.collection.update_many(
            {
                "user_id": object_id,
                "revoked_at": None,
            },
            {
                "$set": {
                    "revoked_at": now,
                    "revoke_reason": reason,
                }
            },
        )

        return result.modified_count

    async def count_active_by_user(
        self,
        user_id: str | ObjectId,
    ) -> int:
        """
        Retorna a quantidade de sessões válidas do usuário.
        """

        try:
            object_id = parse_user_object_id(
                user_id
            )

        except InvalidRefreshUserIdError:
            return 0

        return await self.collection.count_documents(
            {
                "user_id": object_id,
                "revoked_at": None,
                "expires_at": {
                    "$gt": utc_now(),
                },
            }
        )

    async def find_active_by_user(
        self,
        user_id: str | ObjectId,
    ) -> list[dict[str, Any]]:
        """
        Retorna todas as sessões ativas do usuário.

        Pode ser usado futuramente para uma tela de
        dispositivos conectados.
        """

        try:
            object_id = parse_user_object_id(
                user_id
            )

        except InvalidRefreshUserIdError:
            return []

        cursor = self.collection.find(
            {
                "user_id": object_id,
                "revoked_at": None,
                "expires_at": {
                    "$gt": utc_now(),
                },
            }
        ).sort(
            "created_at",
            -1,
        )

        return await cursor.to_list(
            length=100
        )


def get_refresh_session_repository() -> RefreshSessionRepository:
    """
    Retorna uma instância do repository.
    """

    return RefreshSessionRepository()