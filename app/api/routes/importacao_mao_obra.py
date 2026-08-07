from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
)

from app.schemas.importacao_mao_obra import (
    MaoObraImportacaoResponse,
    MaoObraPreviewResponse,
)
from app.services.importacao_mao_obra_service import (
    ImportacaoMaoObraService,
    get_importacao_mao_obra_service,
)


router = APIRouter(
    prefix="/importacoes/mao-de-obra",
    tags=["Importação Mão de Obra"],
)


@router.post(
    "/preview",
    response_model=MaoObraPreviewResponse,
    summary="Validar planilha de mão de obra",
)
async def preview_importacao_mao_obra(
    arquivo: UploadFile = File(...),
    service: ImportacaoMaoObraService = Depends(
        get_importacao_mao_obra_service
    ),
) -> MaoObraPreviewResponse:
    try:
        content = await arquivo.read()

        return service.preview(
            filename=(
                arquivo.filename
                or "arquivo"
            ),
            content=content,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


@router.post(
    "/processar",
    response_model=MaoObraImportacaoResponse,
    summary="Importar mão de obra no Sankhya",
)
async def processar_importacao_mao_obra(
    arquivo: UploadFile = File(...),

    codigo_cliente: int = Form(
        default=46996
    ),

    service: ImportacaoMaoObraService = Depends(
        get_importacao_mao_obra_service
    ),
) -> MaoObraImportacaoResponse:
    try:
        content = await arquivo.read()

        return await service.processar(
            filename=(
                arquivo.filename
                or "arquivo"
            ),
            content=content,
            codigo_cliente=codigo_cliente,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc