import asyncio
import getpass
import sys

from pydantic import ValidationError

from app.core.config import get_settings
from app.core.database import (
    close_mongo,
    connect_to_mongo,
)
from app.repositories.user_repository import (
    UserAlreadyExistsError,
)
from app.schemas.auth import (
    UserCreateRequest,
    UserRole,
)
from app.services.auth_service import (
    get_auth_service,
)


def read_required_input(
    label: str,
) -> str:
    """
    Solicita um valor obrigatório pelo terminal.
    """

    while True:
        value = input(label).strip()

        if value:
            return value

        print("O valor não pode ficar vazio.")


def read_password() -> str:
    """
    Solicita e confirma a senha sem exibi-la no terminal.
    """

    while True:
        password = getpass.getpass(
            "Senha do administrador: "
        )

        password_confirmation = getpass.getpass(
            "Confirme a senha: "
        )

        if password != password_confirmation:
            print(
                "As senhas não conferem. "
                "Tente novamente."
            )
            continue

        return password


async def create_admin() -> None:
    """
    Cria o primeiro usuário administrador.
    """

    settings = get_settings()

    if not settings.mongodb_enabled:
        raise RuntimeError(
            "MongoDB está desabilitado. "
            "Defina MONGODB_ENABLED=true no .env."
        )

    await connect_to_mongo()

    try:
        print()
        print("=" * 50)
        print("CRIAR ADMINISTRADOR")
        print("=" * 50)

        name = read_required_input(
            "Nome do administrador: "
        )

        email = read_required_input(
            "E-mail do administrador: "
        )

        password = read_password()

        try:
            request = UserCreateRequest(
                name=name,
                email=email,
                password=password,
                role=UserRole.ADMIN,
            )

        except ValidationError as exc:
            print()
            print(
                "Não foi possível validar os dados:"
            )

            for error in exc.errors():
                location = ".".join(
                    str(item)
                    for item in error["loc"]
                )

                message = error["msg"]

                print(
                    f"- {location}: {message}"
                )

            sys.exit(1)

        auth_service = get_auth_service()

        try:
            admin = await auth_service.create_user(
                request
            )

        except UserAlreadyExistsError as exc:
            print()
            print(f"Erro: {exc}")
            sys.exit(1)

        print()
        print("=" * 50)
        print("ADMINISTRADOR CRIADO COM SUCESSO")
        print("=" * 50)
        print(f"ID: {admin.id}")
        print(f"Nome: {admin.name}")
        print(f"E-mail: {admin.email}")
        print(f"Perfil: {admin.role}")
        print(f"Ativo: {admin.is_active}")
        print()

    finally:
        await close_mongo()


def main() -> None:
    """
    Ponto de entrada do script.
    """

    try:
        asyncio.run(
            create_admin()
        )

    except KeyboardInterrupt:
        print()
        print("Operação cancelada pelo usuário.")

    except RuntimeError as exc:
        print()
        print(f"Erro: {exc}")
        sys.exit(1)

    except Exception as exc:
        print()
        print(
            "Erro inesperado ao criar administrador:"
        )
        print(
            f"{type(exc).__name__}: {exc}"
        )
        sys.exit(1)


if __name__ == "__main__":
    main()