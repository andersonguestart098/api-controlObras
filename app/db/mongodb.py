from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.core.config import get_settings


_client: AsyncIOMotorClient | None = None
_database: AsyncIOMotorDatabase | None = None


async def connect_mongodb() -> None:
    global _client, _database
    settings = get_settings()
    _client = AsyncIOMotorClient(settings.mongodb_url)
    _database = _client[settings.mongodb_database]
    await _database.command("ping")


async def disconnect_mongodb() -> None:
    global _client, _database
    if _client:
        _client.close()
    _client = None
    _database = None


def get_database() -> AsyncIOMotorDatabase:
    if _database is None:
        raise RuntimeError("MongoDB não inicializado.")
    return _database
