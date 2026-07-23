SELECT
    CAB.NUNOTA,
    CAB.NUMNOTA,
    CAB.DTNEG,

    CAB.CODPROJ,
    PRJ.IDENTIFICACAO AS PROJETO,

    CAB.CODPARC,
    PAR.RAZAOSOCIAL AS PARCEIRO,
    PAR.CGC_CPF,

    CAB.CODTIPOPER,
    TOP.DESCROPER,

    'VENDA INTERNO OBRAS' AS TIPO_MOVIMENTO,

    CAB.CODTIPVENDA,
    TPV.DESCRTIPVENDA AS TIPO_NEGOCIACAO,

    NVL(CAB.VLRNOTA, 0) AS VLRNOTA,
    NVL(CAB.VLRICMS, 0) AS VLRICMS,
    NVL(CAB.VLRPIS, 0) AS VLRPIS,
    NVL(CAB.VLRCOFINS, 0) AS VLRCOFINS,

    /*
     * Custo total dos itens da nota:
     *
     * quantidade negociada
     * × último custo médio sem ICMS
     */
    NVL(
        CUSTO.CUSTO_MEDIO_SEM_ICMS_TOTAL,
        0
    ) AS CUSTO_MEDIO_SEM_ICMS_TOTAL,

    17.00 AS PERC_GASTO_FIXO,
    3.35 AS PERC_IRPJ_CSSL,
    3.50 AS PERC_COMISSAO,

    ROUND(
        NVL(CAB.VLRNOTA, 0) * 0.17,
        2
    ) AS VLR_GASTO_FIXO,

    ROUND(
        NVL(CAB.VLRNOTA, 0) * 0.0335,
        2
    ) AS VLR_IRPJ_CSSL,

    ROUND(
        NVL(CAB.VLRNOTA, 0) * 0.035,
        2
    ) AS VLR_COMISSAO,

    ROUND(
          NVL(CAB.VLRICMS, 0)
        + NVL(CAB.VLRPIS, 0)
        + NVL(CAB.VLRCOFINS, 0)
        + NVL(CAB.VLRNOTA, 0) * 0.17
        + NVL(CAB.VLRNOTA, 0) * 0.0335
        + NVL(CAB.VLRNOTA, 0) * 0.035,
        2
    ) AS VLR_GASTO_TOTAL,

    ROUND(
        NVL(CAB.VLRNOTA, 0)
        - (
              NVL(CAB.VLRICMS, 0)
            + NVL(CAB.VLRPIS, 0)
            + NVL(CAB.VLRCOFINS, 0)
            + NVL(CAB.VLRNOTA, 0) * 0.17
            + NVL(CAB.VLRNOTA, 0) * 0.0335
            + NVL(CAB.VLRNOTA, 0) * 0.035
        ),
        2
    ) AS VLR_LIQUIDO,

    /*
     * Resultado após encargos e custo.
     */
    ROUND(
        NVL(CAB.VLRNOTA, 0)
        - (
              NVL(CAB.VLRICMS, 0)
            + NVL(CAB.VLRPIS, 0)
            + NVL(CAB.VLRCOFINS, 0)
            + NVL(CAB.VLRNOTA, 0) * 0.17
            + NVL(CAB.VLRNOTA, 0) * 0.0335
            + NVL(CAB.VLRNOTA, 0) * 0.035
            + NVL(
                CUSTO.CUSTO_MEDIO_SEM_ICMS_TOTAL,
                0
              )
        ),
        2
    ) AS RESULTADO_APOS_CUSTO

FROM TGFCAB CAB

LEFT JOIN TGFTOP TOP
       ON TOP.CODTIPOPER = CAB.CODTIPOPER
      AND TOP.DHALTER = CAB.DHTIPOPER

LEFT JOIN TGFTPV TPV
       ON TPV.CODTIPVENDA = CAB.CODTIPVENDA
      AND TPV.DHALTER = CAB.DHTIPVENDA

LEFT JOIN TGFPAR PAR
       ON PAR.CODPARC = CAB.CODPARC

LEFT JOIN TCSPRJ PRJ
       ON PRJ.CODPROJ = CAB.CODPROJ

/*
 * Agrupa os custos por nota para manter
 * a granularidade principal em uma linha por nota.
 */
LEFT JOIN (
    SELECT
        ITE.NUNOTA,

        ROUND(
            SUM(
                NVL(ITE.QTDNEG, 0)
                * NVL(CUS.CUSSEMICM, 0)
            ),
            2
        ) AS CUSTO_MEDIO_SEM_ICMS_TOTAL

    FROM TGFITE ITE

    INNER JOIN TGFCAB CAB_CUSTO
            ON CAB_CUSTO.NUNOTA = ITE.NUNOTA

    LEFT JOIN TGFCUS CUS
           ON CUS.CODPROD = ITE.CODPROD
          AND CUS.CODEMP = CAB_CUSTO.CODEMP
          AND CUS.DTATUAL = (
              SELECT MAX(C2.DTATUAL)
              FROM TGFCUS C2
              WHERE C2.CODPROD = ITE.CODPROD
                AND C2.CODEMP = CAB_CUSTO.CODEMP
          )

    GROUP BY
        ITE.NUNOTA
) CUSTO
       ON CUSTO.NUNOTA = CAB.NUNOTA

WHERE CAB.CODTIPOPER IN (
    1101,
    1164,
    1166
)
  AND CAB.CODTIPVENDA = 323
  AND CAB.CODPROJ = {{CODPROJ}}

/*FILTRO_DTNEG_INICIAL*/
/*FILTRO_DTNEG_FINAL*/
/*FILTRO_NUNOTA*/

ORDER BY
    CAB.DTNEG,
    CAB.NUNOTA