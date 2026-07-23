from pathlib import Path

from app.schemas.query import QueryGranularity, SankhyaQueryDefinition


SQL_DIR = Path(__file__).parent / "sql"


QUERY_REGISTRY: dict[str, SankhyaQueryDefinition] = {
    "pagamentos": SankhyaQueryDefinition(
        code="pagamentos",
        name="Pagamentos e títulos da obra",
        filename="pagamentos.sql",
        granularity=QueryGranularity.TITULO,
        expected_columns=["NUNOTA", "NUFIN", "CODPROJ", "VALOR_TITULO", "VALOR_BAIXA", "SALDO_ABERTO", "STATUS_TITULO"],
    ),
    "notas": SankhyaQueryDefinition(
        code="notas",
        name="Notas de venda e devolução",
        filename="notas.sql",
        granularity=QueryGranularity.NOTA,
        expected_columns=["NUNOTA", "CODPROJ", "TIPO_MOVIMENTO", "VLRNOTA", "VLR_LIQUIDO"],
    ),
    "itens_notas": SankhyaQueryDefinition(
        code="itens_notas",
        name="Itens de notas com impostos e custo",
        filename="itens_notas.sql",
        granularity=QueryGranularity.ITEM,
        expected_columns=["NUNOTA", "SEQUENCIA", "CODPROD", "CODPROJ", "VLR_ITEM_LIQUIDO", "CUSTO_MEDIO_SEM_ICMS_TOTAL"],
    ),
    "itens_remessas": SankhyaQueryDefinition(
        code="itens_remessas",
        name="Itens de remessas, entrega e saldo",
        filename="itens_remessas.sql",
        granularity=QueryGranularity.ITEM,
        expected_columns=["NUNOTA", "CODPROD", "QTD_TOTAL", "QTD_ENTREGUE", "QTD_PENDENTE", "STATUS_ITEM"],
        supports_period=False,
        supports_nunota=False,
    ),
    "compras": SankhyaQueryDefinition(
        code="compras",
        name="Compras vinculadas à obra",
        filename="compras.sql",
        granularity=QueryGranularity.NOTA,
        expected_columns=["NUNOTA", "CODPROJ", "TIPO_MOVIMENTO", "VLRNOTA", "VLR_LIQUIDO"],
        supports_period=False,
        supports_nunota=False,
    ),
    "remessas": SankhyaQueryDefinition(
        code="remessas",
        name="Remessas vinculadas à obra",
        filename="remessas.sql",
        granularity=QueryGranularity.NOTA,
        expected_columns=["NUNOTA", "CODPROJ", "TIPO_MOVIMENTO", "VLRNOTA", "VLR_LIQUIDO"],
        supports_period=False,
        supports_nunota=False,
    ),
    "pagamento_interno_obras": SankhyaQueryDefinition(
    code="pagamento_interno_obras",
    name="Vendas com plano Interno Obras",
    filename="pagamento_interno_obras.sql",
    granularity=QueryGranularity.NOTA,
    expected_columns=[
        "NUNOTA",
        "CODPROJ",
        "TIPO_MOVIMENTO",
        "VLRNOTA",
        "CUSTO_MEDIO_SEM_ICMS_TOTAL",
        "VLR_LIQUIDO",
        "RESULTADO_APOS_CUSTO",
    ],
    supports_period=False,
    supports_nunota=False,
    ),

    "notas_impostos": SankhyaQueryDefinition(
    code="notas_impostos",
    name="Impostos e comissão das notas da obra",
    filename="notas_impostos.sql",
    granularity=QueryGranularity.NOTA,
    expected_columns=[
        "NUNOTA",
        "CODPROJ",
        "TIPO_MOVIMENTO",
        "VLRNOTA",
        "VLR_ICMS",
        "VLR_PIS",
        "VLR_COFINS",
        "VLR_TOTAL_TRIBUTOS",
        "VLR_COMISSAO",
    ],
    supports_period=True,
    supports_nunota=False,
    ),

    "projeto": SankhyaQueryDefinition(
        code="projeto",
        name="Identificação do projeto",
        filename="projeto.sql",
        granularity=QueryGranularity.PROJETO,
        expected_columns=[
            "CODPROJ",
            "NOME_PROJETO",
        ],
        supports_period=False,
        supports_nunota=False,
    ),


}


def load_sql(definition: SankhyaQueryDefinition) -> str:
    return (SQL_DIR / definition.filename).read_text(encoding="utf-8")
