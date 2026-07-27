SELECT *
FROM (
    WITH RELACOES AS (
        SELECT DISTINCT
            VAR.NUNOTAORIG,
            VAR.NUNOTA
        FROM TGFVAR VAR
    ),

    BASE_RELACAO_RAW AS (
        SELECT
            P1009.NUNOTA AS PEDIDO_MAE_NUNOTA,
            P1009.NUMNOTA AS PEDIDO_MAE_NUMNOTA,

            CAB.NUNOTA AS PEDIDO_1010_NUNOTA,
            CAB.NUMNOTA AS PEDIDO_1010_NUMNOTA,

            /*
             * A nota principal desta consulta agora
             * é a TOP 1010.
             *
             * Mantemos o alias CAB para o serviço
             * conseguir aplicar CAB.DTNEG nos
             * filtros dinâmicos de período.
             */
            CAB.NUNOTA,
            CAB.NUMNOTA,
            CAB.DANFE,
            CAB.DTNEG,
            CAB.CODEMP,

            P1009.CODPROJ AS CODPROJ,

            CAB.CODPARC,
            CAB.CODTIPOPER,
            CAB.DHTIPOPER,

            CAB.CODTIPVENDA,
            CAB.DHTIPVENDA,

            NVL(CAB.VLRNOTA, 0) AS VLRNOTA,

            ROW_NUMBER() OVER (
                PARTITION BY CAB.NUNOTA
                ORDER BY
                    P1009.NUNOTA,
                    CAB.NUNOTA
            ) AS RN

        FROM TGFCAB P1009

        INNER JOIN RELACOES VAR_1009_1010
                ON VAR_1009_1010.NUNOTAORIG =
                   P1009.NUNOTA

        INNER JOIN TGFCAB CAB
                ON CAB.NUNOTA =
                   VAR_1009_1010.NUNOTA
               AND CAB.CODTIPOPER = 1010

        WHERE P1009.CODTIPOPER = 1009
          AND NVL(P1009.CODTIPVENDA, 0) <> 323
          AND P1009.CODPROJ = {{CODPROJ}}

        /*FILTRO_DTNEG_INICIAL*/
        /*FILTRO_DTNEG_FINAL*/
    ),

    BASE_RELACAO AS (
        SELECT
            PEDIDO_MAE_NUNOTA,
            PEDIDO_MAE_NUMNOTA,

            PEDIDO_1010_NUNOTA,
            PEDIDO_1010_NUMNOTA,

            NUNOTA,
            NUMNOTA,
            DANFE,
            DTNEG,
            CODEMP,
            CODPROJ,

            CODPARC,
            CODTIPOPER,
            DHTIPOPER,

            CODTIPVENDA,
            DHTIPVENDA,

            VLRNOTA

        FROM BASE_RELACAO_RAW
        WHERE RN = 1
    ),

    IMPOSTOS AS (
        SELECT
            BASE.NUNOTA,

            ROUND(
                SUM(
                    CASE
                        WHEN DIN.CODIMP = 1
                            THEN NVL(DIN.BASE, 0)
                        ELSE 0
                    END
                ),
                2
            ) AS BASE_ICMS,

            ROUND(
                SUM(
                    CASE
                        WHEN DIN.CODIMP = 1
                            THEN NVL(DIN.VALOR, 0)
                        ELSE 0
                    END
                ),
                2
            ) AS VLRICMS,

            ROUND(
                SUM(
                    CASE
                        WHEN DIN.CODIMP = 6
                            THEN NVL(DIN.BASE, 0)
                        ELSE 0
                    END
                ),
                2
            ) AS BASE_PIS,

            ROUND(
                SUM(
                    CASE
                        WHEN DIN.CODIMP = 6
                            THEN NVL(DIN.VALOR, 0)
                        ELSE 0
                    END
                ),
                2
            ) AS VLRPIS,

            ROUND(
                SUM(
                    CASE
                        WHEN DIN.CODIMP = 7
                            THEN NVL(DIN.BASE, 0)
                        ELSE 0
                    END
                ),
                2
            ) AS BASE_COFINS,

            ROUND(
                SUM(
                    CASE
                        WHEN DIN.CODIMP = 7
                            THEN NVL(DIN.VALOR, 0)
                        ELSE 0
                    END
                ),
                2
            ) AS VLRCOFINS

        FROM BASE_RELACAO BASE

        LEFT JOIN TGFDIN DIN
               ON DIN.NUNOTA = BASE.NUNOTA
              AND DIN.CODIMP IN (1, 6, 7)

        GROUP BY
            BASE.NUNOTA
    ),

    CUSTOS AS (
        SELECT
            BASE.NUNOTA,

            ROUND(
                SUM(
                    (
                        CASE
                            WHEN VOA.DIVIDEMULTIPLICA = 'D'
                                THEN NVL(ITE.QTDNEG, 0)
                                     * NVL(
                                         VOA.QUANTIDADE,
                                         1
                                     )

                            WHEN VOA.DIVIDEMULTIPLICA = 'M'
                                THEN NVL(ITE.QTDNEG, 0)
                                     / NULLIF(
                                         NVL(
                                             VOA.QUANTIDADE,
                                             1
                                         ),
                                         0
                                     )

                            ELSE NVL(ITE.QTDNEG, 0)
                        END
                    )
                    * NVL(CUS.CUSSEMICM, 0)
                ),
                2
            ) AS CUSTO_MEDIO_SEM_ICMS_TOTAL

        FROM BASE_RELACAO BASE

        INNER JOIN TGFITE ITE
                ON ITE.NUNOTA = BASE.NUNOTA

        LEFT JOIN TGFVOA VOA
               ON VOA.CODPROD = ITE.CODPROD
              AND VOA.CODVOL = ITE.CODVOL
              AND NVL(VOA.ATIVO, 'S') = 'S'

        LEFT JOIN (
            SELECT
                ULTIMO.CODEMP,
                ULTIMO.CODPROD,
                ULTIMO.CUSSEMICM

            FROM (
                SELECT
                    C.CODEMP,
                    C.CODPROD,
                    C.CUSSEMICM,

                    ROW_NUMBER() OVER (
                        PARTITION BY
                            C.CODEMP,
                            C.CODPROD
                        ORDER BY
                            C.DTATUAL DESC
                    ) AS RN

                FROM TGFCUS C
            ) ULTIMO

            WHERE ULTIMO.RN = 1
        ) CUS
               ON CUS.CODEMP = BASE.CODEMP
              AND CUS.CODPROD = ITE.CODPROD

        GROUP BY
            BASE.NUNOTA
    )

    SELECT
        BASE.PEDIDO_MAE_NUNOTA,
        BASE.PEDIDO_MAE_NUMNOTA,

        BASE.PEDIDO_1010_NUNOTA,
        BASE.PEDIDO_1010_NUMNOTA,

        BASE.NUNOTA,
        BASE.NUMNOTA,

        TO_CHAR(BASE.DANFE) AS DANFE,

        BASE.DTNEG,
        BASE.CODEMP,

        BASE.CODPROJ,
        PRJ.IDENTIFICACAO AS PROJETO,

        BASE.CODPARC,
        PAR.RAZAOSOCIAL AS PARCEIRO,
        PAR.CGC_CPF,

        BASE.CODTIPOPER,
        TOP.DESCROPER,

        'REMESSA_TRANSPORTE' AS TIPO_MOVIMENTO,

        BASE.CODTIPVENDA,
        TPV.DESCRTIPVENDA AS TIPO_NEGOCIACAO,

        NVL(BASE.VLRNOTA, 0) AS VLRNOTA,

        NVL(IMP.BASE_ICMS, 0) AS BASE_ICMS,

        CASE
            WHEN NVL(IMP.BASE_ICMS, 0) = 0
                THEN 0
            ELSE ROUND(
                NVL(IMP.VLRICMS, 0)
                / IMP.BASE_ICMS
                * 100,
                2
            )
        END AS ALIQ_ICMS,

        NVL(IMP.VLRICMS, 0) AS VLRICMS,

        NVL(IMP.BASE_PIS, 0) AS BASE_PIS,

        CASE
            WHEN NVL(IMP.BASE_PIS, 0) = 0
                THEN 0
            ELSE ROUND(
                NVL(IMP.VLRPIS, 0)
                / IMP.BASE_PIS
                * 100,
                2
            )
        END AS ALIQ_PIS,

        NVL(IMP.VLRPIS, 0) AS VLRPIS,

        NVL(IMP.BASE_COFINS, 0) AS BASE_COFINS,

        CASE
            WHEN NVL(IMP.BASE_COFINS, 0) = 0
                THEN 0
            ELSE ROUND(
                NVL(IMP.VLRCOFINS, 0)
                / IMP.BASE_COFINS
                * 100,
                2
            )
        END AS ALIQ_COFINS,

        NVL(IMP.VLRCOFINS, 0) AS VLRCOFINS,

        ROUND(
            NVL(IMP.VLRPIS, 0)
            + NVL(IMP.VLRCOFINS, 0),
            2
        ) AS VLR_TRIBUTOS_FEDERAIS,

        ROUND(
            NVL(IMP.VLRICMS, 0)
            + NVL(IMP.VLRPIS, 0)
            + NVL(IMP.VLRCOFINS, 0),
            2
        ) AS VLR_TOTAL_TRIBUTOS,

        0.00 AS PERC_GASTO_FIXO,
        0.00 AS PERC_IRPJ_CSSL,
        0.00 AS PERC_COMISSAO,

        0.00 AS VLR_GASTO_FIXO,
        0.00 AS VLR_IRPJ_CSSL,
        0.00 AS VLR_COMISSAO,

        ROUND(
            NVL(IMP.VLRICMS, 0)
            + NVL(IMP.VLRPIS, 0)
            + NVL(IMP.VLRCOFINS, 0),
            2
        ) AS VLR_GASTO_TOTAL,

        NVL(
            CUSTO.CUSTO_MEDIO_SEM_ICMS_TOTAL,
            0
        ) AS CUSTO_MEDIO_SEM_ICMS_TOTAL,

        ROUND(
            NVL(BASE.VLRNOTA, 0)
            - (
                NVL(IMP.VLRICMS, 0)
                + NVL(IMP.VLRPIS, 0)
                + NVL(IMP.VLRCOFINS, 0)
            ),
            2
        ) AS VLR_LIQUIDO,

        ROUND(
            NVL(BASE.VLRNOTA, 0)
            - (
                NVL(IMP.VLRICMS, 0)
                + NVL(IMP.VLRPIS, 0)
                + NVL(IMP.VLRCOFINS, 0)
                + NVL(
                    CUSTO.CUSTO_MEDIO_SEM_ICMS_TOTAL,
                    0
                )
            ),
            2
        ) AS RESULTADO_APOS_CUSTO

    FROM BASE_RELACAO BASE

    LEFT JOIN IMPOSTOS IMP
           ON IMP.NUNOTA = BASE.NUNOTA

    LEFT JOIN CUSTOS CUSTO
           ON CUSTO.NUNOTA = BASE.NUNOTA

    LEFT JOIN TGFTOP TOP
           ON TOP.CODTIPOPER = BASE.CODTIPOPER
          AND TOP.DHALTER = BASE.DHTIPOPER

    LEFT JOIN TGFTPV TPV
           ON TPV.CODTIPVENDA = BASE.CODTIPVENDA
          AND TPV.DHALTER = BASE.DHTIPVENDA

    LEFT JOIN TGFPAR PAR
           ON PAR.CODPARC = BASE.CODPARC

    LEFT JOIN TCSPRJ PRJ
           ON PRJ.CODPROJ = BASE.CODPROJ
) RESULTADO

ORDER BY
    RESULTADO.DTNEG,
    RESULTADO.NUNOTA