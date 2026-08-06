SELECT
    PRJ.CODPROJ,

    TRIM(PRJ.IDENTIFICACAO) AS IDENTIFICACAO,

    TRIM(PRJ.ABREVIATURA) AS ABREVIATURA,

    NVL(
        TRIM(PRJ.IDENTIFICACAO),
        NVL(
            TRIM(PRJ.ABREVIATURA),
            'Projeto ' || PRJ.CODPROJ
        )
    ) AS NOME_PROJETO,

    TO_CHAR(PRJ.CODPROJ)
        || ' - '
        || NVL(
            TRIM(PRJ.IDENTIFICACAO),
            NVL(
                TRIM(PRJ.ABREVIATURA),
                'Projeto ' || PRJ.CODPROJ
            )
        ) AS LABEL_PROJETO

FROM TCSPRJ PRJ

WHERE PRJ.CODPROJ IS NOT NULL

ORDER BY
    NVL(
        TRIM(PRJ.IDENTIFICACAO),
        TRIM(PRJ.ABREVIATURA)
    ),
    PRJ.CODPROJ