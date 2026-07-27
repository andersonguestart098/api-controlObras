SELECT
    CAB.NUNOTA,
    CAB.NUMNOTA,
    CAB.DTNEG,

    CAB.CODEMP,

    CAB.CODPROJ,
    PRJ.IDENTIFICACAO AS PROJETO,

    CAB.CODPARC,
    PAR.RAZAOSOCIAL AS PARCEIRO,
    PAR.CGC_CPF,

    CAB.CODTIPOPER,
    TOP.DESCROPER,

    'DEVOLUCAO_INTERNO_OBRAS'
        AS TIPO_MOVIMENTO,

    CAB.CODTIPVENDA,
    TPV.DESCRTIPVENDA AS TIPO_NEGOCIACAO,

    NVL(
        CAB.VLRNOTA,
        0
    ) AS VLRNOTA,

    /*
     * Impostos reais da nota, buscados na TGFDIN.
     */
    NVL(
        IMP.VLR_ICMS,
        0
    ) AS VLRICMS,

    NVL(
        IMP.VLR_PIS,
        0
    ) AS VLRPIS,

    NVL(
        IMP.VLR_COFINS,
        0
    ) AS VLRCOFINS,

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

    /*
     * Tributos reais da TGFDIN
     * + gasto fixo
     * + IRPJ/CSLL
     * + comissão.
     */
    ROUND(
          NVL(IMP.VLR_ICMS, 0)
        + NVL(IMP.VLR_PIS, 0)
        + NVL(IMP.VLR_COFINS, 0)
        + NVL(CAB.VLRNOTA, 0) * 0.17
        + NVL(CAB.VLRNOTA, 0) * 0.0335
        + NVL(CAB.VLRNOTA, 0) * 0.035,
        2
    ) AS VLR_GASTO_TOTAL,

    /*
     * Valor líquido da devolução antes do custo.
     */
    ROUND(
        NVL(CAB.VLRNOTA, 0)
        - (
              NVL(IMP.VLR_ICMS, 0)
            + NVL(IMP.VLR_PIS, 0)
            + NVL(IMP.VLR_COFINS, 0)
            + NVL(CAB.VLRNOTA, 0) * 0.17
            + NVL(CAB.VLRNOTA, 0) * 0.0335
            + NVL(CAB.VLRNOTA, 0) * 0.035
        ),
        2
    ) AS VLR_LIQUIDO,

    /*
     * Custo médio total dos produtos devolvidos.
     */
    NVL(
        CUSTO_NOTA.CUSTO_MEDIO_SEM_ICMS_TOTAL,
        0
    ) AS CUSTO_MEDIO_SEM_ICMS_TOTAL,

    /*
     * Resultado líquido após impostos,
     * encargos e custo dos produtos.
     */
    ROUND(
        (
            NVL(CAB.VLRNOTA, 0)
            - (
                  NVL(IMP.VLR_ICMS, 0)
                + NVL(IMP.VLR_PIS, 0)
                + NVL(IMP.VLR_COFINS, 0)
                + NVL(CAB.VLRNOTA, 0) * 0.17
                + NVL(CAB.VLRNOTA, 0) * 0.0335
                + NVL(CAB.VLRNOTA, 0) * 0.035
            )
        )
        - NVL(
            CUSTO_NOTA.CUSTO_MEDIO_SEM_ICMS_TOTAL,
            0
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
 * Impostos da nota de devolução.
 *
 * CODIMP 1 = ICMS
 * CODIMP 6 = PIS
 * CODIMP 7 = COFINS
 */
LEFT JOIN (
    SELECT
        DIN.NUNOTA,

        ROUND(
            SUM(
                CASE
                    WHEN DIN.CODIMP = 1
                        THEN NVL(DIN.VALOR, 0)
                    ELSE 0
                END
            ),
            2
        ) AS VLR_ICMS,

        ROUND(
            SUM(
                CASE
                    WHEN DIN.CODIMP = 6
                        THEN NVL(DIN.VALOR, 0)
                    ELSE 0
                END
            ),
            2
        ) AS VLR_PIS,

        ROUND(
            SUM(
                CASE
                    WHEN DIN.CODIMP = 7
                        THEN NVL(DIN.VALOR, 0)
                    ELSE 0
                END
            ),
            2
        ) AS VLR_COFINS

    FROM TGFDIN DIN

    WHERE DIN.CODIMP IN (
        1,
        6,
        7
    )

    GROUP BY
        DIN.NUNOTA
) IMP
       ON IMP.NUNOTA = CAB.NUNOTA

/*
 * Custo médio total dos itens
 * presentes na nota de devolução.
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

    /*
     * Seleciona somente o custo mais recente
     * de cada produto por empresa.
     */
    LEFT JOIN (
        SELECT
            CODEMP,
            CODPROD,
            CUSSEMICM

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
        )

        WHERE RN = 1
    ) CUS
           ON CUS.CODEMP = CAB_CUSTO.CODEMP
          AND CUS.CODPROD = ITE.CODPROD

    GROUP BY
        ITE.NUNOTA
) CUSTO_NOTA
       ON CUSTO_NOTA.NUNOTA = CAB.NUNOTA

WHERE CAB.CODTIPOPER IN (
    1201,
    1202,
    1257,
    1206
)

  AND CAB.CODPROJ = {{CODPROJ}}

  AND EXISTS (
      SELECT 1

      FROM TGFVAR VAR

      INNER JOIN TGFCAB ORIG
              ON ORIG.NUNOTA =
                 VAR.NUNOTAORIG

      WHERE VAR.NUNOTA =
            CAB.NUNOTA

        AND ORIG.CODTIPVENDA = 323
  )

/*FILTRO_DTNEG_INICIAL*/
/*FILTRO_DTNEG_FINAL*/

ORDER BY
    CAB.DTNEG,
    CAB.NUNOTA