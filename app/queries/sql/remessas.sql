SELECT *
FROM (
    WITH BASE AS (
        SELECT
            CAB.NUNOTA,
            CAB.NUMNOTA,
            CAB.DTNEG,
            CAB.CODEMP,

            CAB.CODPROJ,

            CAB.CODPARC,

            CAB.CODTIPOPER,
            CAB.DHTIPOPER,

            CAB.CODTIPVENDA,
            CAB.DHTIPVENDA,

            NVL(CAB.VLRNOTA, 0)   AS VLRNOTA,
            NVL(CAB.VLRICMS, 0)   AS VLRICMS,
            NVL(CAB.VLRPIS, 0)    AS VLRPIS,
            NVL(CAB.VLRCOFINS, 0) AS VLRCOFINS

        FROM TGFCAB CAB

        WHERE CAB.CODTIPOPER = 1009
          AND NVL(CAB.CODTIPVENDA, 0) <> 323
          AND CAB.CODPROJ = {{CODPROJ}}
    ),

    /*
     * CUSTO DA PRÓPRIA NOTA-MÃE.
     *
     * Mesma lógica de custo já usada em
     * remessas_transporte.sql: quantidade
     * convertida pela unidade e multiplicada
     * pelo último custo médio sem ICMS.
     *
     * É este valor que alimenta a coluna
     * "Valor custo" da Remessa futura.
     */
    CUSTOS AS (
        SELECT
            BASE.NUNOTA,

            ROUND(
                SUM(
                    (
                        CASE
                            WHEN VOA.DIVIDEMULTIPLICA = 'D'
                                THEN NVL(ITE.QTDNEG, 0)
                                     * NVL(VOA.QUANTIDADE, 1)

                            WHEN VOA.DIVIDEMULTIPLICA = 'M'
                                THEN NVL(ITE.QTDNEG, 0)
                                     / NULLIF(
                                         NVL(VOA.QUANTIDADE, 1),
                                         0
                                     )

                            ELSE NVL(ITE.QTDNEG, 0)
                        END
                    )
                    * NVL(CUS.CUSSEMICM, 0)
                ),
                2
            ) AS CUSTO_MEDIO_SEM_ICMS_TOTAL

        FROM BASE

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
        BASE.NUNOTA,
        BASE.NUMNOTA,
        BASE.DTNEG,
        BASE.CODEMP,

        BASE.CODPROJ,
        PRJ.IDENTIFICACAO AS PROJETO,

        BASE.CODPARC,
        PAR.RAZAOSOCIAL AS PARCEIRO,
        PAR.CGC_CPF,

        BASE.CODTIPOPER,
        TOP.DESCROPER,

        'REMESSA' AS TIPO_MOVIMENTO,

        BASE.CODTIPVENDA,
        TPV.DESCRTIPVENDA AS TIPO_NEGOCIACAO,

        BASE.VLRNOTA,
        BASE.VLRICMS,
        BASE.VLRPIS,
        BASE.VLRCOFINS,

        17.00 AS PERC_GASTO_FIXO,
        3.35  AS PERC_IRPJ_CSSL,
        3.50  AS PERC_COMISSAO,

        ROUND(
            BASE.VLRNOTA * 0.17,
            2
        ) AS VLR_GASTO_FIXO,

        ROUND(
            BASE.VLRNOTA * 0.0335,
            2
        ) AS VLR_IRPJ_CSSL,

        ROUND(
            BASE.VLRNOTA * 0.035,
            2
        ) AS VLR_COMISSAO,

        ROUND(
              BASE.VLRICMS
            + BASE.VLRPIS
            + BASE.VLRCOFINS
            + BASE.VLRNOTA * 0.17
            + BASE.VLRNOTA * 0.0335
            + BASE.VLRNOTA * 0.035,
            2
        ) AS VLR_GASTO_TOTAL,

        NVL(
            CUSTO.CUSTO_MEDIO_SEM_ICMS_TOTAL,
            0
        ) AS CUSTO_MEDIO_SEM_ICMS_TOTAL,

        ROUND(
            BASE.VLRNOTA
            - (
                  BASE.VLRICMS
                + BASE.VLRPIS
                + BASE.VLRCOFINS
                + BASE.VLRNOTA * 0.17
                + BASE.VLRNOTA * 0.0335
                + BASE.VLRNOTA * 0.035
            ),
            2
        ) AS VLR_LIQUIDO,

        ROUND(
            BASE.VLRNOTA
            - (
                  BASE.VLRICMS
                + BASE.VLRPIS
                + BASE.VLRCOFINS
                + BASE.VLRNOTA * 0.17
                + BASE.VLRNOTA * 0.0335
                + BASE.VLRNOTA * 0.035
                + NVL(
                    CUSTO.CUSTO_MEDIO_SEM_ICMS_TOTAL,
                    0
                )
            ),
            2
        ) AS RESULTADO_APOS_CUSTO

    FROM BASE

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