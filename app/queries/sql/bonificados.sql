WITH CUSTO_ATUAL AS (
    SELECT
        CUS.CODEMP,
        CUS.CODPROD,

        MAX(CUS.CUSSEMICM)
            KEEP (
                DENSE_RANK LAST
                ORDER BY CUS.DTATUAL
            ) AS CUSSEMICM

    FROM TGFCUS CUS

    GROUP BY
        CUS.CODEMP,
        CUS.CODPROD
),

CUSTO_NOTA AS (
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

    LEFT JOIN CUSTO_ATUAL CUS
           ON CUS.CODEMP = CAB_CUSTO.CODEMP
          AND CUS.CODPROD = ITE.CODPROD

    WHERE CAB_CUSTO.CODTIPOPER = 1151

      AND NVL(
            CAB_CUSTO.CODTIPVENDA,
            0
          ) <> 323

      AND CAB_CUSTO.CODPROJ = {{CODPROJ}}

    GROUP BY
        ITE.NUNOTA
)

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

    'BONIFICADO' AS TIPO_MOVIMENTO,

    CAB.CODTIPVENDA,
    TPV.DESCRTIPVENDA AS TIPO_NEGOCIACAO,

    NVL(CAB.VLRNOTA, 0) AS VLRNOTA,

    NVL(CAB.VLRICMS, 0) AS VLRICMS,
    NVL(CAB.VLRPIS, 0) AS VLRPIS,
    NVL(CAB.VLRCOFINS, 0) AS VLRCOFINS,

    NVL(
        CST.CUSTO_MEDIO_SEM_ICMS_TOTAL,
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
        + (
            NVL(CAB.VLRNOTA, 0)
            * 0.17
          )
        + (
            NVL(CAB.VLRNOTA, 0)
            * 0.0335
          )
        + (
            NVL(CAB.VLRNOTA, 0)
            * 0.035
          ),
        2
    ) AS VLR_GASTO_TOTAL,

    ROUND(
        NVL(CAB.VLRNOTA, 0)
        - (
              NVL(CAB.VLRICMS, 0)
            + NVL(CAB.VLRPIS, 0)
            + NVL(CAB.VLRCOFINS, 0)
            + (
                NVL(CAB.VLRNOTA, 0)
                * 0.17
              )
            + (
                NVL(CAB.VLRNOTA, 0)
                * 0.0335
              )
            + (
                NVL(CAB.VLRNOTA, 0)
                * 0.035
              )
          ),
        2
    ) AS VLR_LIQUIDO

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

LEFT JOIN CUSTO_NOTA CST
       ON CST.NUNOTA = CAB.NUNOTA

WHERE CAB.CODTIPOPER = 1151

  /* Exclui tipo de negociação Interno Obras */
  AND NVL(CAB.CODTIPVENDA, 0) <> 323

  AND CAB.CODPROJ = {{CODPROJ}}

ORDER BY
    CAB.DTNEG,
    CAB.NUNOTA