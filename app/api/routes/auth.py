from fastapi import APIRouter, Depends

from app.core.security import validar_api_key
from app.services.sankhya_auth import (
    SankhyaAuthService,
    get_sankhya_auth_service,
)


router = APIRouter(
    prefix="/sankhya/auth",
    tags=["Sankhya Auth"],
    dependencies=[Depends(validar_api_key)],
)


@router.post("/token")
async def gerar_ou_renovar_token(
    forcar_renovacao: bool = False,
    auth_service: SankhyaAuthService = Depends(
        get_sankhya_auth_service
    ),
) -> dict[str, object]:
    """
    Sem forçar:
        retorna/reutiliza o token atual e só autentica se expirado.

    Forçando:
        solicita um novo token imediatamente.
    """

    if forcar_renovacao:
        await auth_service.refresh_token(
            force=True,
        )
    else:
        await auth_service.get_token()

    return {
        "autenticado": True,
        "renovacao_forcada": forcar_renovacao,
        "expira_em_utc": auth_service.token_expiration,
    }