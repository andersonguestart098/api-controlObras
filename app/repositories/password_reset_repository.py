from datetime import datetime
from typing import Any

from bson import ObjectId
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from app.core.database import get_database
from app.core.security import utc_now


class PasswordResetTokenAlreadyExistsError(Exception):
    """
    Erro extremamente raro caso o hash do token
    já exista no MongoDB.
    """

    pass


class InvalidPasswordResetUserIdError(Exception):
    """
    Erro lançado quando o ID do usuário não possui
    formato válido de ObjectId.
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
        raise InvalidPasswordResetUserIdError(
            "ID do usuário inválido."
        )

    return ObjectId(user_id)


class PasswordResetRepository:
    """
    Responsável pela coleção password_resets.

    O token original nunca é salvo no MongoDB.
    Somente o hash SHA-256 do token é armazenado.
    """

    @property
    def collection(self) -> Any:
        """
        Retorna a coleção password_resets.
        """

        database = get_database()

        return database["password_resets"]

    async def create(
        self,
        *,
        user_id: str | ObjectId,
        token_hash: str,
        expires_at: datetime,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> dict[str, Any]:
        """
        Cria um novo token de recuperação de senha.

        Antes de criar o novo token, invalida tokens
        anteriores ainda ativos do mesmo usuário.
        """

        object_id = parse_user_object_id(user_id)

        now = utc_now()

        await self.invalidate_all_by_user(
            user_id=object_id,
            reason="NEW_RESET_TOKEN_REQUESTED",
        )

        reset_document: dict[str, Any] = {
            "user_id": object_id,
            "token_hash": token_hash,

            "created_at": now,
            "expires_at": expires_at,

            # Token de uso único.
            "used_at": None,

            # Pode ser invalidado antes de ser utilizado.
            "invalidated_at": None,
            "invalidate_reason": None,

            # Informações opcionais de auditoria.
            "ip_address": ip_address,
            "user_agent": user_agent,
        }

        try:
            result = await self.collection.insert_one(
                reset_document
            )

        except DuplicateKeyError as exc:
            raise PasswordResetTokenAlreadyExistsError(
                "Já existe uma recuperação com esse token."
            ) from exc

        reset_document["_id"] = result.inserted_id

        return reset_document

    async def find_by_token_hash(
        self,
        token_hash: str,
    ) -> dict[str, Any] | None:
        """
        Busca um token pelo hash independentemente
        de estar ativo, utilizado ou expirado.
        """

        return await self.collection.find_one(
            {
                "token_hash": token_hash,
            }
        )

    async def find_valid_by_token_hash(
        self,
        token_hash: str,
    ) -> dict[str, Any] | None:
        """
        Busca somente um token de recuperação válido.

        Para ser válido, ele precisa:

        - não ter sido utilizado;
        - não ter sido invalidado;
        - não estar expirado.
        """

        return await self.collection.find_one(
            {
                "token_hash": token_hash,
                "used_at": None,
                "invalidated_at": None,
                "expires_at": {
                    "$gt": utc_now(),
                },
            }
        )

    async def consume(
        self,
        token_hash: str,
    ) -> dict[str, Any] | None:
        """
        Consome atomicamente um token de recuperação.

        O filtro impede que duas requisições simultâneas
        consigam utilizar o mesmo token.

        Retorna o documento já marcado como utilizado.
        """

        now = utc_now()

        return await self.collection.find_one_and_update(
            {
                "token_hash": token_hash,
                "used_at": None,
                "invalidated_at": None,
                "expires_at": {
                    "$gt": now,
                },
            },
            {
                "$set": {
                    "used_at": now,
                }
            },
            return_document=ReturnDocument.AFTER,
        )

    async def invalidate_by_token_hash(
        self,
        *,
        token_hash: str,
        reason: str = "TOKEN_INVALIDATED",
    ) -> dict[str, Any] | None:
        """
        Invalida um token específico que ainda não
        tenha sido utilizado.
        """

        now = utc_now()

        return await self.collection.find_one_and_update(
            {
                "token_hash": token_hash,
                "used_at": None,
                "invalidated_at": None,
            },
            {
                "$set": {
                    "invalidated_at": now,
                    "invalidate_reason": reason,
                }
            },
            return_document=ReturnDocument.AFTER,
        )

    async def invalidate_all_by_user(
        self,
        *,
        user_id: str | ObjectId,
        reason: str = "ALL_RESET_TOKENS_INVALIDATED",
    ) -> int:
        """
        Invalida todos os tokens ainda ativos de um usuário.

        Isso será utilizado quando:

        - um novo token for solicitado;
        - a senha for redefinida;
        - o usuário for desativado.
        """

        try:
            object_id = parse_user_object_id(user_id)

        except InvalidPasswordResetUserIdError:
            return 0

        now = utc_now()

        result = await self.collection.update_many(
            {
                "user_id": object_id,
                "used_at": None,
                "invalidated_at": None,
            },
            {
                "$set": {
                    "invalidated_at": now,
                    "invalidate_reason": reason,
                }
            },
        )

        return result.modified_count

    async def count_valid_by_user(
        self,
        user_id: str | ObjectId,
    ) -> int:
        """
        Retorna a quantidade de tokens válidos do usuário.
        Normalmente será zero ou um.
        """

        try:
            object_id = parse_user_object_id(user_id)

        except InvalidPasswordResetUserIdError:
            return 0

        return await self.collection.count_documents(
            {
                "user_id": object_id,
                "used_at": None,
                "invalidated_at": None,
                "expires_at": {
                    "$gt": utc_now(),
                },
            }
        )


def get_password_reset_repository() -> PasswordResetRepository:
    """
    Retorna uma instância do repository.
    """

    return PasswordResetRepository()