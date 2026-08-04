from typing import Any

from pymongo import ASCENDING, AsyncMongoClient
from pymongo.errors import PyMongoError

from app.core.config import get_settings


class MongoDatabase:
    """
    Mantém o cliente e a referência do banco MongoDB
    durante todo o ciclo de vida da aplicação.

    O cliente é aberto na inicialização do FastAPI
    e fechado durante o encerramento.
    """

    def __init__(self) -> None:
        self.client: AsyncMongoClient | None = None
        self.database: Any | None = None

    @property
    def is_connected(self) -> bool:
        """
        Informa se o cliente e o banco foram inicializados.
        """

        return (
            self.client is not None
            and self.database is not None
        )


mongo = MongoDatabase()


async def create_auth_indexes(database: Any) -> None:
    """
    Cria os índices necessários para o fluxo de autenticação.

    Coleções utilizadas:

    - users
    - refresh_sessions
    - password_resets

    A criação é idempotente: se o índice já existir com
    a mesma configuração, o MongoDB simplesmente o mantém.
    """

    # =====================================================
    # USERS
    # =====================================================

    # Impede o cadastro de dois usuários com o mesmo e-mail.
    #
    # O e-mail será sempre salvo normalizado:
    # email.strip().lower()
    await database.users.create_index(
        [
            ("email", ASCENDING),
        ],
        unique=True,
        name="uq_users_email",
    )

    # Facilita consultas de usuários ativos por perfil.
    await database.users.create_index(
        [
            ("is_active", ASCENDING),
            ("role", ASCENDING),
        ],
        name="ix_users_active_role",
    )

    # =====================================================
    # REFRESH SESSIONS
    # =====================================================

    # Cada refresh token deve possuir um hash único.
    await database.refresh_sessions.create_index(
        [
            ("token_hash", ASCENDING),
        ],
        unique=True,
        name="uq_refresh_sessions_token_hash",
    )

    # Facilita a busca das sessões de um usuário.
    await database.refresh_sessions.create_index(
        [
            ("user_id", ASCENDING),
            ("revoked_at", ASCENDING),
        ],
        name="ix_refresh_sessions_user_revoked",
    )

    # Facilita a busca pelo grupo/família do refresh token.
    #
    # Isso será útil para rotação de refresh token e
    # detecção de reutilização de tokens antigos.
    await database.refresh_sessions.create_index(
        [
            ("family_id", ASCENDING),
        ],
        name="ix_refresh_sessions_family_id",
    )

    # Índice TTL.
    #
    # Quando expires_at for atingido, o MongoDB poderá
    # remover automaticamente o documento expirado.
    await database.refresh_sessions.create_index(
        [
            ("expires_at", ASCENDING),
        ],
        expireAfterSeconds=0,
        name="ttl_refresh_sessions_expires_at",
    )

    # =====================================================
    # PASSWORD RESETS
    # =====================================================

    # Cada token de recuperação possui um hash único.
    await database.password_resets.create_index(
        [
            ("token_hash", ASCENDING),
        ],
        unique=True,
        name="uq_password_resets_token_hash",
    )

    # Facilita a localização dos tokens de recuperação
    # pertencentes a um usuário.
    await database.password_resets.create_index(
        [
            ("user_id", ASCENDING),
            ("used_at", ASCENDING),
        ],
        name="ix_password_resets_user_used",
    )

    # Remove automaticamente tokens de recuperação
    # depois da data de expiração.
    await database.password_resets.create_index(
        [
            ("expires_at", ASCENDING),
        ],
        expireAfterSeconds=0,
        name="ttl_password_resets_expires_at",
    )


async def connect_to_mongo() -> None:
    """
    Abre a conexão com o MongoDB.

    Essa função deverá ser chamada no lifespan do FastAPI.
    """

    settings = get_settings()

    if not settings.mongodb_enabled:
        print(
            "MongoDB desabilitado: "
            "MONGODB_ENABLED=false"
        )
        return

    if mongo.is_connected:
        return

    try:
        mongo.client = AsyncMongoClient(
            settings.mongodb_uri.get_secret_value(),

            # Retorna datas do MongoDB com timezone UTC.
            tz_aware=True,

            # Tempo máximo para localizar um servidor
            # disponível no cluster.
            serverSelectionTimeoutMS=10_000,

            # Tempo máximo para abrir uma conexão.
            connectTimeoutMS=10_000,

            # Tempo máximo aguardando uma resposta.
            socketTimeoutMS=30_000,

            # Representação padronizada para UUIDs.
            uuidRepresentation="standard",
        )

        # O AsyncMongoClient é inicializado de forma
        # preguiçosa. O ping força uma conexão real.
        await mongo.client.admin.command("ping")

        mongo.database = mongo.client[
            settings.mongodb_database
        ]

        await create_auth_indexes(
            mongo.database
        )

        print(
            "MongoDB conectado com sucesso: "
            f"{settings.mongodb_database}"
        )

    except PyMongoError as exc:
        mongo.client = None
        mongo.database = None

        raise RuntimeError(
            "Não foi possível conectar ao MongoDB. "
            "Verifique MONGODB_URI, usuário, senha, "
            "Network Access e permissões do Atlas."
        ) from exc


async def close_mongo() -> None:
    """
    Fecha a conexão com o MongoDB.

    Essa função deverá ser chamada no encerramento
    do lifespan do FastAPI.
    """

    if mongo.client is None:
        return

    try:
        await mongo.client.close()

    finally:
        mongo.client = None
        mongo.database = None

        print(
            "Conexão com MongoDB encerrada."
        )


def get_database() -> Any:
    """
    Retorna a instância do banco MongoDB.

    Essa função será utilizada dentro dos repositories.

    Exemplo:

        database = get_database()
        usuario = await database.users.find_one(...)
    """

    if mongo.database is None:
        raise RuntimeError(
            "MongoDB não está conectado. "
            "Verifique se connect_to_mongo() foi chamado "
            "durante a inicialização da aplicação."
        )

    return mongo.database


def get_collection(
    collection_name: str,
) -> Any:
    """
    Retorna uma coleção específica do MongoDB.

    Exemplo:

        users = get_collection('users')
    """

    if not collection_name.strip():
        raise ValueError(
            "O nome da coleção não pode ser vazio."
        )

    database = get_database()

    return database[
        collection_name.strip()
    ]