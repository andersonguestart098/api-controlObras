SELECT
    z.NUNOTA,
    z.NUMNOTA,
    z.SEQUENCIA,
    z.CODPROD,
    z.DESCRPROD,
    z.CODVOL,
    z.QTD_TOTAL,
    z.QTD_ENTREGUE,
    z.QTD_PENDENTE,
    z.PRECO_LIQ_UNITARIO,
    z.CUSTO_MEDIO_SEM_ICMS,
    z.CUSTO_TOTAL,
    z.CUSTO_ENTREGUE,
    z.CUSTO_PENDENTE,
    z.VLR_TOTAL_ITEM,
    z.VLR_ENTREGUE_ITEM,
    z.VLR_SALDO_ITEM,
    z.PERC_ENTREGA,
    z.STATUS_ITEM

FROM (
    SELECT
        x.NUNOTA,
        x.NUMNOTA,
        x.SEQUENCIA,
        TO_CHAR(x.CODPROD) AS CODPROD,
        x.DESCRPROD,
        x.CODVOL,
        x.QTD_TOTAL,
        x.QTD_ENTREGUE,
        x.QTD_PENDENTE,
        x.PRECO_LIQ_UNITARIO,
        x.CUSTO_MEDIO_SEM_ICMS,

        ROUND(
            NVL(x.CUSTO_MEDIO_SEM_ICMS, 0)
            * NVL(x.QTD_TOTAL, 0),
            2
        ) AS CUSTO_TOTAL,

        ROUND(
            NVL(x.CUSTO_MEDIO_SEM_ICMS, 0)
            * NVL(x.QTD_ENTREGUE, 0),
            2
        ) AS CUSTO_ENTREGUE,

        ROUND(
            NVL(x.CUSTO_MEDIO_SEM_ICMS, 0)
            * NVL(x.QTD_PENDENTE, 0),
            2
        ) AS CUSTO_PENDENTE,

        x.VLR_TOTAL_ITEM,
        x.VLR_ENTREGUE_ITEM,
        x.VLR_SALDO_ITEM,

        CASE
            WHEN NVL(x.QTD_TOTAL, 0) = 0 THEN 0
            ELSE ROUND(
                NVL(x.QTD_ENTREGUE, 0)
                / x.QTD_TOTAL * 100,
                2
            )
        END AS PERC_ENTREGA,

        CASE
            WHEN NVL(x.QTD_PENDENTE, 0) = 0
             AND NVL(x.QTD_ENTREGUE, 0) > 0
                THEN 'ENTREGUE'

            WHEN NVL(x.QTD_ENTREGUE, 0) > 0
             AND NVL(x.QTD_PENDENTE, 0) > 0
                THEN 'PARCIAL'

            ELSE 'NAO ENTREGUE'
        END AS STATUS_ITEM,

        1 AS ORDEM

    FROM (
        SELECT
            p1009.NUNOTA,
            p1009.NUMNOTA,
            ite.SEQUENCIA,
            ite.CODPROD,
            pro.DESCRPROD,
            ite.CODVOL,

            SUM(
                CASE
                    WHEN voa.DIVIDEMULTIPLICA = 'D'
                        THEN NVL(ite.QTDNEG, 0)
                             * NVL(voa.QUANTIDADE, 1)

                    WHEN voa.DIVIDEMULTIPLICA = 'M'
                        THEN NVL(ite.QTDNEG, 0)
                             / NULLIF(NVL(voa.QUANTIDADE, 1), 0)

                    ELSE NVL(ite.QTDNEG, 0)
                END
            ) AS QTD_TOTAL,

            SUM(
                CASE
                    WHEN voa.DIVIDEMULTIPLICA = 'D'
                        THEN NVL(ite.QTDENTREGUE, 0)
                             * NVL(voa.QUANTIDADE, 1)

                    WHEN voa.DIVIDEMULTIPLICA = 'M'
                        THEN NVL(ite.QTDENTREGUE, 0)
                             / NULLIF(NVL(voa.QUANTIDADE, 1), 0)

                    ELSE NVL(ite.QTDENTREGUE, 0)
                END
            ) AS QTD_ENTREGUE,

            SUM(
                CASE
                    WHEN voa.DIVIDEMULTIPLICA = 'D'
                        THEN GREATEST(
                                 NVL(ite.QTDNEG, 0)
                                 - NVL(ite.QTDENTREGUE, 0),
                                 0
                             ) * NVL(voa.QUANTIDADE, 1)

                    WHEN voa.DIVIDEMULTIPLICA = 'M'
                        THEN GREATEST(
                                 NVL(ite.QTDNEG, 0)
                                 - NVL(ite.QTDENTREGUE, 0),
                                 0
                             ) / NULLIF(NVL(voa.QUANTIDADE, 1), 0)

                    ELSE GREATEST(
                             NVL(ite.QTDNEG, 0)
                             - NVL(ite.QTDENTREGUE, 0),
                             0
                         )
                END
            ) AS QTD_PENDENTE,

            ROUND(
                CASE
                    WHEN SUM(
                        CASE
                            WHEN voa.DIVIDEMULTIPLICA = 'D'
                                THEN NVL(ite.QTDNEG, 0)
                                     * NVL(voa.QUANTIDADE, 1)

                            WHEN voa.DIVIDEMULTIPLICA = 'M'
                                THEN NVL(ite.QTDNEG, 0)
                                     / NULLIF(
                                         NVL(voa.QUANTIDADE, 1),
                                         0
                                     )

                            ELSE NVL(ite.QTDNEG, 0)
                        END
                    ) = 0
                        THEN 0

                    ELSE
                        SUM(
                            NVL(ite.VLRTOT, 0)
                            - NVL(ite.VLRDESC, 0)
                            - NVL(ite.VLRREPRED, 0)
                        )
                        /
                        SUM(
                            CASE
                                WHEN voa.DIVIDEMULTIPLICA = 'D'
                                    THEN NVL(ite.QTDNEG, 0)
                                         * NVL(voa.QUANTIDADE, 1)

                                WHEN voa.DIVIDEMULTIPLICA = 'M'
                                    THEN NVL(ite.QTDNEG, 0)
                                         / NULLIF(
                                             NVL(voa.QUANTIDADE, 1),
                                             0
                                         )

                                ELSE NVL(ite.QTDNEG, 0)
                            END
                        )
                END,
                6
            ) AS PRECO_LIQ_UNITARIO,

            ROUND(
                MAX(NVL(cus.CUSSEMICM, 0)),
                6
            ) AS CUSTO_MEDIO_SEM_ICMS,

            SUM(
                NVL(ite.VLRTOT, 0)
                - NVL(ite.VLRDESC, 0)
                - NVL(ite.VLRREPRED, 0)
            ) AS VLR_TOTAL_ITEM,

            SUM(
                CASE
                    WHEN NVL(ite.QTDNEG, 0) = 0 THEN 0
                    ELSE
                        (
                            NVL(ite.VLRTOT, 0)
                            - NVL(ite.VLRDESC, 0)
                            - NVL(ite.VLRREPRED, 0)
                        )
                        / NVL(ite.QTDNEG, 0)
                        * NVL(ite.QTDENTREGUE, 0)
                END
            ) AS VLR_ENTREGUE_ITEM,

            SUM(
                CASE
                    WHEN NVL(ite.QTDNEG, 0) = 0 THEN 0
                    ELSE
                        (
                            NVL(ite.VLRTOT, 0)
                            - NVL(ite.VLRDESC, 0)
                            - NVL(ite.VLRREPRED, 0)
                        )
                        / NVL(ite.QTDNEG, 0)
                        * GREATEST(
                            NVL(ite.QTDNEG, 0)
                            - NVL(ite.QTDENTREGUE, 0),
                            0
                        )
                END
            ) AS VLR_SALDO_ITEM

        FROM TGFCAB p1009

        INNER JOIN TGFITE ite
                ON ite.NUNOTA = p1009.NUNOTA

        INNER JOIN TGFPRO pro
                ON pro.CODPROD = ite.CODPROD

        LEFT JOIN TGFVOA voa
               ON voa.CODPROD = ite.CODPROD
              AND voa.CODVOL = ite.CODVOL
              AND NVL(voa.ATIVO, 'S') = 'S'

        LEFT JOIN (
            SELECT
                c.CODEMP,
                c.CODPROD,
                c.CUSSEMICM
            FROM (
                SELECT
                    c1.CODEMP,
                    c1.CODPROD,
                    c1.CUSSEMICM,

                    ROW_NUMBER() OVER (
                        PARTITION BY
                            c1.CODEMP,
                            c1.CODPROD
                        ORDER BY
                            c1.DTATUAL DESC
                    ) AS RN

                FROM TGFCUS c1
            ) c
            WHERE c.RN = 1
        ) cus
               ON cus.CODEMP = p1009.CODEMP
              AND cus.CODPROD = ite.CODPROD

        WHERE p1009.CODTIPOPER = 1009
          AND p1009.CODPROJ = {{CODPROJ}}

        GROUP BY
            p1009.NUNOTA,
            p1009.NUMNOTA,
            ite.SEQUENCIA,
            ite.CODPROD,
            pro.DESCRPROD,
            ite.CODVOL
    ) x

    UNION ALL

    SELECT
        NULL AS NUNOTA,
        NULL AS NUMNOTA,
        NULL AS SEQUENCIA,
        NULL AS CODPROD,
        'TOTAL GERAL' AS DESCRPROD,
        NULL AS CODVOL,

        SUM(x.QTD_TOTAL) AS QTD_TOTAL,
        SUM(x.QTD_ENTREGUE) AS QTD_ENTREGUE,
        SUM(x.QTD_PENDENTE) AS QTD_PENDENTE,

        NULL AS PRECO_LIQ_UNITARIO,
        NULL AS CUSTO_MEDIO_SEM_ICMS,

        ROUND(
            SUM(
                NVL(x.CUSTO_MEDIO_SEM_ICMS, 0)
                * NVL(x.QTD_TOTAL, 0)
            ),
            2
        ) AS CUSTO_TOTAL,

        ROUND(
            SUM(
                NVL(x.CUSTO_MEDIO_SEM_ICMS, 0)
                * NVL(x.QTD_ENTREGUE, 0)
            ),
            2
        ) AS CUSTO_ENTREGUE,

        ROUND(
            SUM(
                NVL(x.CUSTO_MEDIO_SEM_ICMS, 0)
                * NVL(x.QTD_PENDENTE, 0)
            ),
            2
        ) AS CUSTO_PENDENTE,

        SUM(x.VLR_TOTAL_ITEM) AS VLR_TOTAL_ITEM,
        SUM(x.VLR_ENTREGUE_ITEM) AS VLR_ENTREGUE_ITEM,
        SUM(x.VLR_SALDO_ITEM) AS VLR_SALDO_ITEM,

        CASE
            WHEN SUM(x.QTD_TOTAL) = 0 THEN 0
            ELSE ROUND(
                SUM(x.QTD_ENTREGUE)
                / SUM(x.QTD_TOTAL) * 100,
                2
            )
        END AS PERC_ENTREGA,

        'TOTAL' AS STATUS_ITEM,
        2 AS ORDEM

    FROM (
        SELECT
            p1009.NUNOTA,
            p1009.NUMNOTA,
            ite.SEQUENCIA,
            ite.CODPROD,
            pro.DESCRPROD,
            ite.CODVOL,

            SUM(
                CASE
                    WHEN voa.DIVIDEMULTIPLICA = 'D'
                        THEN NVL(ite.QTDNEG, 0)
                             * NVL(voa.QUANTIDADE, 1)

                    WHEN voa.DIVIDEMULTIPLICA = 'M'
                        THEN NVL(ite.QTDNEG, 0)
                             / NULLIF(NVL(voa.QUANTIDADE, 1), 0)

                    ELSE NVL(ite.QTDNEG, 0)
                END
            ) AS QTD_TOTAL,

            SUM(
                CASE
                    WHEN voa.DIVIDEMULTIPLICA = 'D'
                        THEN NVL(ite.QTDENTREGUE, 0)
                             * NVL(voa.QUANTIDADE, 1)

                    WHEN voa.DIVIDEMULTIPLICA = 'M'
                        THEN NVL(ite.QTDENTREGUE, 0)
                             / NULLIF(NVL(voa.QUANTIDADE, 1), 0)

                    ELSE NVL(ite.QTDENTREGUE, 0)
                END
            ) AS QTD_ENTREGUE,

            SUM(
                CASE
                    WHEN voa.DIVIDEMULTIPLICA = 'D'
                        THEN GREATEST(
                                 NVL(ite.QTDNEG, 0)
                                 - NVL(ite.QTDENTREGUE, 0),
                                 0
                             ) * NVL(voa.QUANTIDADE, 1)

                    WHEN voa.DIVIDEMULTIPLICA = 'M'
                        THEN GREATEST(
                                 NVL(ite.QTDNEG, 0)
                                 - NVL(ite.QTDENTREGUE, 0),
                                 0
                             ) / NULLIF(NVL(voa.QUANTIDADE, 1), 0)

                    ELSE GREATEST(
                             NVL(ite.QTDNEG, 0)
                             - NVL(ite.QTDENTREGUE, 0),
                             0
                         )
                END
            ) AS QTD_PENDENTE,

            ROUND(
                MAX(NVL(cus.CUSSEMICM, 0)),
                6
            ) AS CUSTO_MEDIO_SEM_ICMS,

            SUM(
                NVL(ite.VLRTOT, 0)
                - NVL(ite.VLRDESC, 0)
                - NVL(ite.VLRREPRED, 0)
            ) AS VLR_TOTAL_ITEM,

            SUM(
                CASE
                    WHEN NVL(ite.QTDNEG, 0) = 0 THEN 0
                    ELSE
                        (
                            NVL(ite.VLRTOT, 0)
                            - NVL(ite.VLRDESC, 0)
                            - NVL(ite.VLRREPRED, 0)
                        )
                        / NVL(ite.QTDNEG, 0)
                        * NVL(ite.QTDENTREGUE, 0)
                END
            ) AS VLR_ENTREGUE_ITEM,

            SUM(
                CASE
                    WHEN NVL(ite.QTDNEG, 0) = 0 THEN 0
                    ELSE
                        (
                            NVL(ite.VLRTOT, 0)
                            - NVL(ite.VLRDESC, 0)
                            - NVL(ite.VLRREPRED, 0)
                        )
                        / NVL(ite.QTDNEG, 0)
                        * GREATEST(
                            NVL(ite.QTDNEG, 0)
                            - NVL(ite.QTDENTREGUE, 0),
                            0
                        )
                END
            ) AS VLR_SALDO_ITEM

        FROM TGFCAB p1009

        INNER JOIN TGFITE ite
                ON ite.NUNOTA = p1009.NUNOTA

        INNER JOIN TGFPRO pro
                ON pro.CODPROD = ite.CODPROD

        LEFT JOIN TGFVOA voa
               ON voa.CODPROD = ite.CODPROD
              AND voa.CODVOL = ite.CODVOL
              AND NVL(voa.ATIVO, 'S') = 'S'

        LEFT JOIN (
            SELECT
                c.CODEMP,
                c.CODPROD,
                c.CUSSEMICM
            FROM (
                SELECT
                    c1.CODEMP,
                    c1.CODPROD,
                    c1.CUSSEMICM,

                    ROW_NUMBER() OVER (
                        PARTITION BY
                            c1.CODEMP,
                            c1.CODPROD
                        ORDER BY
                            c1.DTATUAL DESC
                    ) AS RN

                FROM TGFCUS c1
            ) c
            WHERE c.RN = 1
        ) cus
               ON cus.CODEMP = p1009.CODEMP
              AND cus.CODPROD = ite.CODPROD

        WHERE p1009.CODTIPOPER = 1009
          AND p1009.CODPROJ = {{CODPROJ}}

        GROUP BY
            p1009.NUNOTA,
            p1009.NUMNOTA,
            ite.SEQUENCIA,
            ite.CODPROD,
            pro.DESCRPROD,
            ite.CODVOL
    ) x
) z

ORDER BY
    z.ORDEM,
    z.NUNOTA,
    z.SEQUENCIA