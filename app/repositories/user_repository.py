from typing import Any

from bson import ObjectId
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from app.core.database import get_database
from app.core.security import utc_now


class UserAlreadyExistsError(Exception):
    """
    Erro lançado quando já existe um usuário
    cadastrado com o mesmo e-mail.
    """

    pass


class InvalidUserIdError(Exception):
    """
    Erro lançado quando um ID não possui
    o formato válido de ObjectId do MongoDB.
    """

    pass


def normalize_email(email: str) -> str:
    """
    Normaliza o e-mail antes de consultar ou salvar.

    Exemplo:

        " ANDERSON@EMPRESA.COM "

    vira:

        "anderson@empresa.com"
    """

    return email.strip().lower()


def parse_object_id(
    user_id: str | ObjectId,
) -> ObjectId:
    """
    Converte uma string para ObjectId.

    Caso o valor já seja ObjectId, apenas o retorna.
    """

    if isinstance(user_id, ObjectId):
        return user_id

    if not ObjectId.is_valid(user_id):
        raise InvalidUserIdError(
            "ID do usuário inválido."
        )

    return ObjectId(user_id)


class UserRepository:
    """
    Responsável exclusivamente pelo acesso à coleção users.

    Regras de autenticação, senha e geração de tokens ficarão
    no AuthService. O repository apenas consulta e altera dados.
    """

    @property
    def collection(self) -> Any:
        """
        Retorna a coleção users do MongoDB.
        """

        database = get_database()

        return database["users"]

    async def create(
        self,
        *,
        name: str,
        email: str,
        password_hash: str,
        role: str = "USER",
        is_active: bool = True,
        avatar_url: str | None = None,
    ) -> dict[str, Any]:
        """
        Cadastra um novo usuário.
        """

        normalized_email = normalize_email(email)
        normalized_role = role.strip().upper()

        if normalized_role not in {
            "ADMIN",
            "USER",
        }:
            raise ValueError(
                "Perfil de usuário inválido."
            )

        now = utc_now()

        user_document: dict[str, Any] = {
            "name": " ".join(name.strip().split()),
            "email": normalized_email,
            "password_hash": password_hash,
            "role": normalized_role,
            "is_active": is_active,
            "avatar_url": avatar_url,

            # Incrementado quando precisamos invalidar
            # todos os access tokens antigos do usuário.
            "token_version": 0,

            "created_at": now,
            "updated_at": now,
            "last_login_at": None,
        }

        try:
            result = await self.collection.insert_one(
                user_document
            )

        except DuplicateKeyError as exc:
            raise UserAlreadyExistsError(
                "Já existe um usuário cadastrado "
                "com esse e-mail."
            ) from exc

        user_document["_id"] = result.inserted_id

        return user_document

    async def find_by_email(
        self,
        email: str,
    ) -> dict[str, Any] | None:
        """
        Busca um usuário pelo e-mail.
        """

        return await self.collection.find_one(
            {
                "email": normalize_email(email),
            }
        )

    async def find_by_id(
        self,
        user_id: str | ObjectId,
    ) -> dict[str, Any] | None:
        """
        Busca um usuário pelo ID.
        """

        try:
            object_id = parse_object_id(user_id)

        except InvalidUserIdError:
            return None

        return await self.collection.find_one(
            {
                "_id": object_id,
            }
        )

    async def exists_by_email(
        self,
        email: str,
    ) -> bool:
        """
        Verifica se já existe um usuário com o e-mail.
        """

        user = await self.collection.find_one(
            {
                "email": normalize_email(email),
            },
            {
                "_id": 1,
            },
        )

        return user is not None

    async def update_last_login(
        self,
        user_id: str | ObjectId,
    ) -> dict[str, Any] | None:
        """
        Atualiza a data do último login.
        """

        try:
            object_id = parse_object_id(user_id)

        except InvalidUserIdError:
            return None

        now = utc_now()

        return await self.collection.find_one_and_update(
            {
                "_id": object_id,
            },
            {
                "$set": {
                    "last_login_at": now,
                    "updated_at": now,
                }
            },
            return_document=ReturnDocument.AFTER,
        )

    async def update_password(
        self,
        *,
        user_id: str | ObjectId,
        password_hash: str,
    ) -> dict[str, Any] | None:
        """
        Atualiza a senha do usuário.

        Também incrementa token_version para invalidar
        access tokens emitidos antes da troca da senha.
        """

        try:
            object_id = parse_object_id(user_id)

        except InvalidUserIdError:
            return None

        return await self.collection.find_one_and_update(
            {
                "_id": object_id,
            },
            {
                "$set": {
                    "password_hash": password_hash,
                    "updated_at": utc_now(),
                },
                "$inc": {
                    "token_version": 1,
                },
            },
            return_document=ReturnDocument.AFTER,
        )

    async def update_password_hash_only(
        self,
        *,
        user_id: str | ObjectId,
        password_hash: str,
    ) -> bool:
        """
        Atualiza somente o hash da senha.

        Utilizado quando o usuário fez login corretamente,
        mas o pwdlib informou que o hash precisa ser
        atualizado para parâmetros mais modernos.

        Não incrementa token_version porque a senha
        original não foi alterada.
        """

        try:
            object_id = parse_object_id(user_id)

        except InvalidUserIdError:
            return False

        result = await self.collection.update_one(
            {
                "_id": object_id,
            },
            {
                "$set": {
                    "password_hash": password_hash,
                    "updated_at": utc_now(),
                }
            },
        )

        return result.matched_count == 1

    async def increment_token_version(
        self,
        user_id: str | ObjectId,
    ) -> dict[str, Any] | None:
        """
        Invalida todos os access tokens emitidos anteriormente.

        O token só será aceito quando o campo ver do JWT
        for igual ao token_version salvo no usuário.
        """

        try:
            object_id = parse_object_id(user_id)

        except InvalidUserIdError:
            return None

        return await self.collection.find_one_and_update(
            {
                "_id": object_id,
            },
            {
                "$inc": {
                    "token_version": 1,
                },
                "$set": {
                    "updated_at": utc_now(),
                },
            },
            return_document=ReturnDocument.AFTER,
        )

    async def set_active(
        self,
        *,
        user_id: str | ObjectId,
        is_active: bool,
    ) -> dict[str, Any] | None:
        """
        Ativa ou desativa um usuário.

        Ao desativar, também incrementa token_version
        para invalidar os access tokens antigos.
        """

        try:
            object_id = parse_object_id(user_id)

        except InvalidUserIdError:
            return None

        update: dict[str, Any] = {
            "$set": {
                "is_active": is_active,
                "updated_at": utc_now(),
            }
        }

        if not is_active:
            update["$inc"] = {
                "token_version": 1,
            }

        return await self.collection.find_one_and_update(
            {
                "_id": object_id,
            },
            update,
            return_document=ReturnDocument.AFTER,
        )

    async def update_role(
        self,
        *,
        user_id: str | ObjectId,
        role: str,
    ) -> dict[str, Any] | None:
        """
        Altera o perfil do usuário.

        A mudança do perfil incrementa token_version porque
        tokens antigos ainda podem conter o perfil anterior.
        """

        normalized_role = role.strip().upper()

        if normalized_role not in {
            "ADMIN",
            "USER",
        }:
            raise ValueError(
                "Perfil de usuário inválido."
            )

        try:
            object_id = parse_object_id(user_id)

        except InvalidUserIdError:
            return None

        return await self.collection.find_one_and_update(
            {
                "_id": object_id,
            },
            {
                "$set": {
                    "role": normalized_role,
                    "updated_at": utc_now(),
                },
                "$inc": {
                    "token_version": 1,
                },
            },
            return_document=ReturnDocument.AFTER,
        )

    async def count_users(self) -> int:
        """
        Retorna a quantidade total de usuários.

        Será útil para validar a criação do primeiro
        administrador pelo script.
        """

        return await self.collection.count_documents({})


def get_user_repository() -> UserRepository:
    """
    Factory usada para obter o repository.

    Posteriormente poderá ser utilizada com Depends
    ou diretamente dentro do AuthService.
    """

    return UserRepository()