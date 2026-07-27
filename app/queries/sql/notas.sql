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

    CASE
        WHEN CAB.CODTIPOPER IN (
            1101,
            1107,
            1164,
            1166
        )
            THEN 'VENDA'

        WHEN CAB.CODTIPOPER IN (
            1201,
            1202,
            1257,
            1206
        )
            THEN 'DEVOLUCAO'
    END AS TIPO_MOVIMENTO,

    CAB.CODTIPVENDA,
    TPV.DESCRTIPVENDA AS TIPO_NEGOCIACAO,

    NVL(CAB.VLRNOTA, 0) AS VLRNOTA,
    NVL(CAB.VLRICMS, 0) AS VLRICMS,
    NVL(CAB.VLRPIS, 0) AS VLRPIS,
    NVL(CAB.VLRCOFINS, 0) AS VLRCOFINS,

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

WHERE CAB.CODPROJ = {{CODPROJ}}

  AND (
        (
            CAB.CODTIPOPER IN (
                1101,
                1107,
                1164,
                1166
            )

            AND NVL(
                CAB.CODTIPVENDA,
                0
            ) <> 323
        )

        OR

        (
            CAB.CODTIPOPER IN (
                1201,
                1202,
                1257,
                1206
            )

            AND NVL(
                CAB.CODTIPVENDA,
                0
            ) <> 323

            AND NOT EXISTS (
                SELECT 1

                FROM TGFVAR VAR

                INNER JOIN TGFCAB ORIG
                        ON ORIG.NUNOTA =
                           VAR.NUNOTAORIG

                WHERE VAR.NUNOTA =
                      CAB.NUNOTA

                  AND ORIG.CODTIPVENDA = 323
            )
        )
  )

/*FILTRO_DTNEG_INICIAL*/
/*FILTRO_DTNEG_FINAL*/

ORDER BY
    CAB.DTNEG,
    CAB.NUNOTA