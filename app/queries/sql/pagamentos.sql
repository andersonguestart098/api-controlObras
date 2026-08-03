SELECT
    DADOS.NUNOTA,
    DADOS.NUFIN,
    DADOS.PARCELA,

    DADOS.DTNEG,
    DADOS.DTVENC,
    DADOS.DHBAIXA,

    DADOS.CODPROJ,
    DADOS.PROJETO,

    DADOS.CODTIPOPER,
    DADOS.DESCROPER,

    DADOS.CODTIPVENDA,
    DADOS.TIPO_NEGOCIACAO,

    DADOS.CODPARC,
    DADOS.PARCEIRO,
    DADOS.CGC_CPF,

    DADOS.RECDESP,

    CASE
        WHEN DADOS.RECDESP = 1
            THEN 'RECEITA'

        WHEN DADOS.RECDESP = -1
            THEN 'DESPESA'

        ELSE 'OUTRO'
    END AS TIPO_FINANCEIRO,

    DADOS.VALOR_TITULO,
    DADOS.VALOR_LIQUIDO,
    DADOS.VALOR_BAIXA,

    DADOS.NUACERTO,
    DADOS.TIPACERTO,

    CASE
        WHEN DADOS.DHBAIXA IS NULL
         AND DADOS.DTVENC < TRUNC(SYSDATE)
            THEN 'VENCIDO'

        WHEN DADOS.DHBAIXA IS NULL
            THEN 'EM ABERTO'

        WHEN DADOS.TIPACERTO = 'C'
            THEN 'QUITADO POR COMPENSACAO FINANCEIRA'

        WHEN DADOS.TIPACERTO = 'V'
            THEN 'QUITADO COM CREDITO DE DEVOLUCAO'

        WHEN DADOS.RECDESP = 1
         AND DADOS.NUBCO_MOVIMENTO IS NOT NULL
         AND DADOS.MBC_RECDESP = 1
            THEN 'RECEBIDO EM CONTA'

        ELSE 'OUTRA FORMA DE BAIXA'
    END AS FORMA_LIQUIDACAO,

    /*
       DINHEIRO EFETIVAMENTE RECEBIDO NA CONTA

       Prioridade:
       1. Valor real do movimento bancário;
       2. Valor da baixa;
       3. Valor líquido do título.
    */
    CASE
        WHEN DADOS.DHBAIXA IS NOT NULL
         AND DADOS.RECDESP = 1
         AND DADOS.TIPACERTO IS NULL
         AND DADOS.NUBCO_MOVIMENTO IS NOT NULL
         AND DADOS.MBC_RECDESP = 1
        THEN ABS(
            NVL(
                NULLIF(DADOS.VLRLANC, 0),
                NVL(
                    NULLIF(DADOS.VALOR_BAIXA, 0),
                    DADOS.VALOR_LIQUIDO
                )
            )
        )

        ELSE 0
    END AS VALOR_RECEBIDO_EM_CONTA,

    /*
       TÍTULO QUITADO POR COMPENSAÇÃO,
       SEM ENTRADA DE DINHEIRO
    */
    CASE
        WHEN DADOS.DHBAIXA IS NOT NULL
         AND DADOS.RECDESP = 1
         AND DADOS.TIPACERTO IN ('C', 'V')
        THEN ABS(
            NVL(
                NULLIF(DADOS.VALOR_BAIXA, 0),
                DADOS.VALOR_LIQUIDO
            )
        )

        ELSE 0
    END AS VALOR_COMPENSADO,

    /*
       VALOR AINDA EM ABERTO,
       INCLUINDO OS TÍTULOS VENCIDOS
    */
    CASE
        WHEN DADOS.DHBAIXA IS NULL
         AND DADOS.RECDESP = 1
        THEN GREATEST(
            ABS(DADOS.VALOR_LIQUIDO)
            - ABS(NVL(DADOS.VALOR_BAIXA, 0)),
            0
        )

        ELSE 0
    END AS VALOR_EM_ABERTO,

    /*
       VALOR VENCIDO E AINDA NÃO PAGO
    */
    CASE
        WHEN DADOS.DHBAIXA IS NULL
         AND DADOS.RECDESP = 1
         AND DADOS.DTVENC < TRUNC(SYSDATE)
        THEN GREATEST(
            ABS(DADOS.VALOR_LIQUIDO)
            - ABS(NVL(DADOS.VALOR_BAIXA, 0)),
            0
        )

        ELSE 0
    END AS VALOR_VENCIDO,

    DADOS.HISTORICO,
    DADOS.VLRLANC,
    DADOS.DTLANC,
    DADOS.MBC_RECDESP,
    DADOS.ORIGMOV,
    DADOS.NUBCO

FROM (
    SELECT
        FIN.NUNOTA,
        FIN.NUFIN,
        FIN.DESDOBRAMENTO AS PARCELA,

        FIN.DTNEG,
        FIN.DTVENC,
        FIN.DHBAIXA,

        CAB.CODPROJ,
        PRJ.IDENTIFICACAO AS PROJETO,

        CAB.CODTIPOPER,
        TOP.DESCROPER,

        CAB.CODTIPVENDA,
        TPV.DESCRTIPVENDA AS TIPO_NEGOCIACAO,

        FIN.CODPARC,
        PAR.RAZAOSOCIAL AS PARCEIRO,
        PAR.CGC_CPF,

        FIN.RECDESP,

        NVL(
            FIN.VLRDESDOB,
            0
        ) AS VALOR_TITULO,

        /*
           MESMA EXPRESSÃO DO CAMPO CALCULADO
           VLRLIQUIDO DO SANKHYA
        */
        (
              NVL(FIN.VLRDESDOB, 0)

            + CASE
                  WHEN FIN.TIPMULTA = '1'
                      THEN NVL(FIN.VLRMULTA, 0)
                  ELSE 0
              END

            + CASE
                  WHEN FIN.TIPJURO = '1'
                      THEN NVL(FIN.VLRJURO, 0)
                  ELSE 0
              END

            + NVL(FIN.DESPCART, 0)
            + NVL(FIN.VLRVENDOR, 0)
            - NVL(FIN.VLRDESC, 0)

            - CASE
                  WHEN FIN.IRFRETIDO = 'S'
                      THEN NVL(FIN.VLRIRF, 0)
                  ELSE 0
              END

            - CASE
                  WHEN FIN.ISSRETIDO = 'S'
                      THEN NVL(FIN.VLRISS, 0)
                  ELSE 0
              END

            - CASE
                  WHEN FIN.INSSRETIDO = 'S'
                      THEN NVL(FIN.VLRINSS, 0)
                  ELSE 0
              END

            - NVL(FIN.CARTAODESC, 0)

            + NVL(
                (
                    SELECT
                        ROUND(
                            SUM(IMF.VALOR * IMF.TIPIMP),
                            2
                        )
                    FROM TGFIMF IMF
                    WHERE IMF.NUFIN = FIN.NUFIN
                ),
                0
            )

            + NVL(FIN.VLRMULTANEGOC, 0)
            + NVL(FIN.VLRJURONEGOC, 0)
            - NVL(FIN.VLRMULTALIB, 0)
            - NVL(FIN.VLRJUROLIB, 0)
            + NVL(FIN.VLRVARCAMBIAL, 0)

        ) * NVL(FIN.RECDESP, 0) AS VALOR_LIQUIDO,

        NVL(
            FIN.VLRBAIXA,
            0
        ) AS VALOR_BAIXA,

        ACER.NUACERTO,
        ACER.TIPACERTO,

        MBC.HISTORICO,
        MBC.VLRLANC,
        MBC.DTLANC,
        MBC.RECDESP AS MBC_RECDESP,
        MBC.ORIGMOV,
        MBC.NUBCO,

        MBC.NUBCO AS NUBCO_MOVIMENTO

    FROM TGFFIN FIN

    INNER JOIN TGFCAB CAB
            ON CAB.NUNOTA = FIN.NUNOTA

    LEFT JOIN TGFTOP TOP
           ON TOP.CODTIPOPER = CAB.CODTIPOPER
          AND TOP.DHALTER = CAB.DHTIPOPER

    LEFT JOIN TGFTPV TPV
           ON TPV.CODTIPVENDA = CAB.CODTIPVENDA
          AND TPV.DHALTER = CAB.DHTIPVENDA

    LEFT JOIN TCSPRJ PRJ
           ON PRJ.CODPROJ = CAB.CODPROJ

    LEFT JOIN TGFPAR PAR
           ON PAR.CODPARC = FIN.CODPARC

    /*
       LEFT JOIN É OBRIGATÓRIO.

       Recebimentos bancários normais podem não possuir
       registro na TGFFRE. A subconsulta retorna apenas
       acertos dos tipos C e V.
    */
    LEFT JOIN (
        SELECT
            FRE.NUFIN,

            MAX(
                CASE
                    WHEN FRE.TIPACERTO IN ('C', 'V')
                        THEN FRE.NUACERTO
                    ELSE NULL
                END
            ) AS NUACERTO,

            MAX(
                CASE
                    WHEN FRE.TIPACERTO IN ('C', 'V')
                        THEN FRE.TIPACERTO
                    ELSE NULL
                END
            ) AS TIPACERTO

        FROM TGFFRE FRE

        GROUP BY
            FRE.NUFIN
    ) ACER
           ON ACER.NUFIN = FIN.NUFIN

    /*
       Movimento financeiro efetivamente registrado
       na conta bancária.
    */
    LEFT JOIN TGFMBC MBC
           ON MBC.NUBCO = FIN.NUBCO

    WHERE CAB.CODTIPOPER IN (
        1101,
        1107,
        1164,
        1166
    )

      AND CAB.CODPROJ = {{CODPROJ}}

    /*FILTRO_DTNEG_INICIAL*/
    /*FILTRO_DTNEG_FINAL*/

) DADOS

ORDER BY
    DADOS.NUNOTA,
    DADOS.DTVENC,
    DADOS.PARCELA