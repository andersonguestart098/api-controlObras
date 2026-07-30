from pathlib import Path

from app.schemas.query import (
    QueryGranularity,
    SankhyaQueryDefinition,
)


SQL_DIR = Path(__file__).parent / "sql"


QUERY_REGISTRY: dict[
    str,
    SankhyaQueryDefinition,
] = {
    "pagamentos": SankhyaQueryDefinition(
        code="pagamentos",
        name="Pagamentos e títulos da obra",
        filename="pagamentos.sql",
        granularity=QueryGranularity.TITULO,
        expected_columns=[
            "NUNOTA",
            "NUFIN",
            "CODPROJ",
            "VALOR_TITULO",
            "VALOR_BAIXA",
            "SALDO_ABERTO",
            "STATUS_TITULO",
        ],
    ),

    "notas": SankhyaQueryDefinition(
        code="notas",
        name="Notas de venda e devolução",
        filename="notas.sql",
        granularity=QueryGranularity.NOTA,
        expected_columns=[
            "NUNOTA",
            "CODPROJ",
            "TIPO_MOVIMENTO",
            "VLRNOTA",
            "VLR_LIQUIDO",
        ],
    ),

    "itens_notas": SankhyaQueryDefinition(
        code="itens_notas",
        name="Itens de notas com impostos e custo",
        filename="itens_notas.sql",
        granularity=QueryGranularity.ITEM,
        expected_columns=[
            "NUNOTA",
            "SEQUENCIA",
            "CODPROD",
            "CODPROJ",
            "VLR_ITEM_LIQUIDO",
            "CUSTO_MEDIO_SEM_ICMS_TOTAL",
        ],
    ),

    "itens_remessas": SankhyaQueryDefinition(
        code="itens_remessas",
        name="Itens de remessas, entrega e saldo",
        filename="itens_remessas.sql",
        granularity=QueryGranularity.ITEM,
        expected_columns=[
            "NUNOTA",
            "CODPROD",
            "QTD_TOTAL",
            "QTD_ENTREGUE",
            "QTD_PENDENTE",
            "STATUS_ITEM",
        ],
        supports_period=False,
    ),

    "compras": SankhyaQueryDefinition(
        code="compras",
        name="Compras vinculadas à obra",
        filename="compras.sql",
        granularity=QueryGranularity.NOTA,
        expected_columns=[
            "NUNOTA",
            "CODPROJ",
            "TIPO_MOVIMENTO",
            "VLRNOTA",
            "VLR_LIQUIDO",
            "CUSTO_MEDIO_SEM_ICMS_TOTAL",
        ],
        supports_period=False,
    ),

    "bonificados": SankhyaQueryDefinition(
        code="bonificados",
        name="Bonificados vinculados à obra",
        filename="bonificados.sql",
        granularity=QueryGranularity.NOTA,
        expected_columns=[
            "NUNOTA",
            "CODPROJ",
            "TIPO_MOVIMENTO",
            "VLRNOTA",
            "VLR_LIQUIDO",
            "CUSTO_MEDIO_SEM_ICMS_TOTAL",
        ],
        supports_period=False,
    ),

    "remessas": SankhyaQueryDefinition(
        code="remessas",
        name="Remessas vinculadas à obra",
        filename="remessas.sql",
        granularity=QueryGranularity.NOTA,
        expected_columns=[
            "NUNOTA",
            "CODPROJ",
            "TIPO_MOVIMENTO",
            "VLRNOTA",
            "VLR_LIQUIDO",
        ],
        supports_period=False,
    ),

    "remessas_transporte": SankhyaQueryDefinition(
        code="remessas_transporte",
        name="Remessas de transporte vinculadas à obra",
        filename="remessas_transporte.sql",
        granularity=QueryGranularity.NOTA,
        expected_columns=[
            "PEDIDO_MAE_NUNOTA",
            "PEDIDO_1010_NUNOTA",
            "NUNOTA",
            "CODPROJ",
            "TIPO_MOVIMENTO",
            "VLRNOTA",
            "VLRICMS",
            "VLRPIS",
            "VLRCOFINS",
            "VLR_TOTAL_TRIBUTOS",
            "VLR_GASTO_TOTAL",
            "VLR_LIQUIDO",
            "CUSTO_MEDIO_SEM_ICMS_TOTAL",
        ],
        supports_period=True,
        supports_nunota=False,
    ),

    "pagamento_interno_obras": (
        SankhyaQueryDefinition(
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
        )
    ),

    "devolucoes_interno_obras": (
        SankhyaQueryDefinition(
            code="devolucoes_interno_obras",
            name="Devoluções do Interno Obras",
            filename=(
                "devolucoes_interno_obras.sql"
            ),
            granularity=QueryGranularity.NOTA,
            expected_columns=[
                "NUNOTA",
                "CODPROJ",
                "TIPO_MOVIMENTO",
                "VLRNOTA",
                "VLRICMS",
                "VLRPIS",
                "VLRCOFINS",
                "VLR_GASTO_FIXO",
                "VLR_IRPJ_CSSL",
                "VLR_COMISSAO",
                "VLR_GASTO_TOTAL",
                "VLR_LIQUIDO",
                "CUSTO_MEDIO_SEM_ICMS_TOTAL",
                "RESULTADO_APOS_CUSTO",
            ],
            supports_period=True,
        )
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
    ),

    "movimentos": SankhyaQueryDefinition(
        code="movimentos",
        name="Movimentos vinculados à obra",
        filename="movimentos.sql",
        granularity=QueryGranularity.NOTA,
        expected_columns=[
            "NUNOTA",
            "NUMNOTA",
            "DTNEG",
            "CODPROJ",
            "PROJETO",
            "CODPARC",
            "PARCEIRO",
            "CGC_CPF",
            "CODTIPOPER",
            "DESCROPER",
            "TIPO_MOVIMENTO",
            "CODTIPVENDA",
            "TIPO_NEGOCIACAO",
            "VLRNOTA",
            "VLRICMS",
            "VLRPIS",
            "VLRCOFINS",
            "VLR_GASTO_FIXO",
            "VLR_IRPJ_CSSL",
            "VLR_COMISSAO",
            "VLR_GASTO_TOTAL",
            "VLR_LIQUIDO",
        ],
        supports_period=True,
    ),

    "mao_de_obra": SankhyaQueryDefinition(
        code="mao_de_obra",
        name="Lançamentos de mão de obra da obra",
        filename="mao_de_obra.sql",
        granularity=QueryGranularity.NOTA,
        expected_columns=[
            "NUNOTA",
            "CODPROJ",
            "TIPO_MOVIMENTO",
            "VLRNOTA",
            "VLRICMS",
            "VLRPIS",
            "VLRCOFINS",
            "VLR_GASTO_FIXO",
            "VLR_IRPJ_CSSL",
            "VLR_COMISSAO",
            "VLR_GASTO_TOTAL",
            "VLR_LIQUIDO",
        ],
        supports_period=True,
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
    ),
}


def load_sql(
    definition: SankhyaQueryDefinition,
) -> str:
    sql_path = SQL_DIR / definition.filename

    return sql_path.read_text(
        encoding="utf-8"
    )