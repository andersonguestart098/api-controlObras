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

    CASE
        WHEN CAB.CODTIPOPER IN (
            1101,
            1164,
            1166
        ) THEN 'VENDA'

        WHEN CAB.CODTIPOPER IN (
            1201,
            1202,
            1257,
            1206
        ) THEN 'DEVOLUCAO'

        WHEN CAB.CODTIPOPER = 1009
            THEN 'REMESSA'

        ELSE 'OUTRO'
    END AS TIPO_MOVIMENTO,

    CAB.CODTIPVENDA,
    TPV.DESCRTIPVENDA AS TIPO_NEGOCIACAO,

    CASE
        WHEN CAB.CODTIPVENDA = 323
            THEN 'S'
        ELSE 'N'
    END AS INTERNO_OBRAS,

    NVL(CAB.VLRNOTA, 0) AS VLRNOTA,

    /* ICMS destacado */
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
        MAX(
            CASE
                WHEN DIN.CODIMP = 1
                    THEN NVL(DIN.ALIQUOTA, 0)
                ELSE 0
            END
        ),
        2
    ) AS ALIQ_ICMS,

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

    /* PIS */
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
        MAX(
            CASE
                WHEN DIN.CODIMP = 6
                    THEN NVL(DIN.ALIQUOTA, 0)
                ELSE 0
            END
        ),
        2
    ) AS ALIQ_PIS,

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

    /* COFINS */
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
        MAX(
            CASE
                WHEN DIN.CODIMP = 7
                    THEN NVL(DIN.ALIQUOTA, 0)
                ELSE 0
            END
        ),
        2
    ) AS ALIQ_COFINS,

    ROUND(
        SUM(
            CASE
                WHEN DIN.CODIMP = 7
                    THEN NVL(DIN.VALOR, 0)
                ELSE 0
            END
        ),
        2
    ) AS VLR_COFINS,

    /* Tributos federais = PIS + COFINS */
    ROUND(
          SUM(
              CASE
                  WHEN DIN.CODIMP = 6
                      THEN NVL(DIN.VALOR, 0)
                  ELSE 0
              END
          )
        + SUM(
              CASE
                  WHEN DIN.CODIMP = 7
                      THEN NVL(DIN.VALOR, 0)
                  ELSE 0
              END
          ),
        2
    ) AS VLR_TRIBUTOS_FEDERAIS,

    /* Total de tributos = ICMS + PIS + COFINS */
    ROUND(
        SUM(
            CASE
                WHEN DIN.CODIMP IN (1, 6, 7)
                    THEN NVL(DIN.VALOR, 0)
                ELSE 0
            END
        ),
        2
    ) AS VLR_TOTAL_TRIBUTOS,

    /* Comissão fixa de 3,5% sobre o valor da nota */
    3.50 AS PERC_COMISSAO,

    ROUND(
        NVL(CAB.VLRNOTA, 0) * 0.035,
        2
    ) AS VLR_COMISSAO,

    /* Valor após tributos e comissão */
    ROUND(
        NVL(CAB.VLRNOTA, 0)
        - (
            SUM(
                CASE
                    WHEN DIN.CODIMP IN (1, 6, 7)
                        THEN NVL(DIN.VALOR, 0)
                    ELSE 0
                END
            )
            + NVL(CAB.VLRNOTA, 0) * 0.035
        ),
        2
    ) AS VLR_APOS_TRIBUTOS_COMISSAO

FROM TGFCAB CAB

LEFT JOIN TGFDIN DIN
       ON DIN.NUNOTA = CAB.NUNOTA
      AND DIN.CODIMP IN (1, 6, 7)

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

  AND CAB.CODTIPOPER IN (
      1009,
      1101,
      1164,
      1166,
      1201,
      1202,
      1257,
      1206
  )

/*FILTRO_DTNEG_INICIAL*/
/*FILTRO_DTNEG_FINAL*/

GROUP BY
    CAB.NUNOTA,
    CAB.NUMNOTA,
    CAB.DTNEG,
    CAB.CODEMP,
    CAB.CODPROJ,
    PRJ.IDENTIFICACAO,
    CAB.CODPARC,
    PAR.RAZAOSOCIAL,
    PAR.CGC_CPF,
    CAB.CODTIPOPER,
    TOP.DESCROPER,
    CAB.CODTIPVENDA,
    TPV.DESCRTIPVENDA,
    CAB.VLRNOTA

ORDER BY
    CAB.DTNEG,
    CAB.NUNOTA