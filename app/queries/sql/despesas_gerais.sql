SELECT
    CAB.NUFIN,
    CAB.NUNOTA,
    CAB.DESDOBRAMENTO AS PARCELA,

    CAB.DTNEG,
    CAB.DTVENC,
    CAB.DHBAIXA,

    CAB.CODPROJ,

    NVL(
        TRIM(PRJ.IDENTIFICACAO),
        NVL(
            TRIM(PRJ.ABREVIATURA),
            'Projeto ' || CAB.CODPROJ
        )
    ) AS PROJETO,

    CAB.CODNAT,
    NAT.DESCRNAT AS NATUREZA,

    CAB.CODPARC,
    PAR.RAZAOSOCIAL AS PARCEIRO,
    PAR.CGC_CPF,

    MBC.HISTORICO,

    /*
       VALOR ORIGINAL DA DESPESA.

       Este é o campo utilizado para calcular
       o total de despesas do projeto.
    */
    ABS(
        NVL(CAB.VLRDESDOB, 0)
    ) AS VALOR_DESPESA,

    /*
       VALOR EFETIVAMENTE BAIXADO NO TÍTULO.

       Não utilizamos MBC.VLRLANC para o total,
       pois um único movimento bancário pode
       liquidar vários títulos.
    */
    CASE
        WHEN CAB.DHBAIXA IS NOT NULL
        THEN ABS(
            NVL(
                NULLIF(CAB.VLRBAIXA, 0),
                CAB.VLRDESDOB
            )
        )
        ELSE 0
    END AS VALOR_PAGO,

    /*
       SALDO DA DESPESA AINDA EM ABERTO.
    */
    CASE
        WHEN CAB.DHBAIXA IS NULL
        THEN GREATEST(
            ABS(
                NVL(CAB.VLRDESDOB, 0)
            )
            -
            ABS(
                NVL(CAB.VLRBAIXA, 0)
            ),
            0
        )
        ELSE 0
    END AS VALOR_EM_ABERTO,

    /*
       SALDO VENCIDO E AINDA NÃO PAGO.
    */
    CASE
        WHEN CAB.DHBAIXA IS NULL
         AND CAB.DTVENC < TRUNC(SYSDATE)
        THEN GREATEST(
            ABS(
                NVL(CAB.VLRDESDOB, 0)
            )
            -
            ABS(
                NVL(CAB.VLRBAIXA, 0)
            ),
            0
        )
        ELSE 0
    END AS VALOR_VENCIDO,

    CASE
        WHEN CAB.DHBAIXA IS NOT NULL
            THEN 'PAGA'

        WHEN CAB.DTVENC < TRUNC(SYSDATE)
            THEN 'VENCIDA'

        ELSE 'EM ABERTO'
    END AS STATUS_DESPESA,

    /*
       Dados bancários apenas informativos.
       Não utilizar VLRLANC para totalizar despesas.
    */
    MBC.VLRLANC AS VALOR_MOVIMENTO_BANCARIO,
    MBC.DTLANC AS DATA_MOVIMENTO,
    MBC.RECDESP AS MBC_RECDESP,
    MBC.ORIGMOV,
    MBC.NUBCO

FROM TGFFIN CAB

LEFT JOIN TCSPRJ PRJ
       ON PRJ.CODPROJ = CAB.CODPROJ

LEFT JOIN TGFNAT NAT
       ON NAT.CODNAT = CAB.CODNAT

LEFT JOIN TGFPAR PAR
       ON PAR.CODPARC = CAB.CODPARC

/*
   Obtém somente o movimento mais recente
   de cada NUBCO, evitando duplicar despesas.
*/
LEFT JOIN (
    SELECT
        MOV.NUBCO,
        MOV.HISTORICO,
        MOV.VLRLANC,
        MOV.DTLANC,
        MOV.RECDESP,
        MOV.ORIGMOV

    FROM (
        SELECT
            M.NUBCO,
            M.HISTORICO,
            M.VLRLANC,
            M.DTLANC,
            M.RECDESP,
            M.ORIGMOV,

            ROW_NUMBER() OVER (
                PARTITION BY M.NUBCO
                ORDER BY
                    M.DTLANC DESC NULLS LAST,
                    M.ROWID DESC
            ) AS RN

        FROM TGFMBC M
    ) MOV

    WHERE MOV.RN = 1
) MBC
       ON MBC.NUBCO = CAB.NUBCO

WHERE CAB.RECDESP = -1

  AND CAB.CODPROJ = {{CODPROJ}}

  /*
     DESCONSIDERA LANÇAMENTOS COM NATUREZA
     DE RECEITA DE VENDAS.

     O código 1001 é a natureza identificada
     atualmente como RECEITAS DE VENDAS.
  */
  AND NVL(CAB.CODNAT, 0) <> 1001

  AND UPPER(
        TRIM(
            NVL(
                NAT.DESCRNAT,
                'SEM NATUREZA'
            )
        )
      ) NOT IN (
        'RECEITA DE VENDAS',
        'RECEITAS DE VENDAS',
        'RECEITA VENDAS'
      )

  /*FILTRO_DTNEG_INICIAL*/
  /*FILTRO_DTNEG_FINAL*/

ORDER BY
    CAB.DTNEG DESC,
    CAB.DTVENC DESC,
    CAB.NUFIN DESC