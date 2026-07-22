from typing import Any

import polars as pl


DATE_HINTS = (
    "DT",
    "DATA",
    "DH",
)

NUMERIC_HINTS = (
    "VLR",
    "VALOR",
    "QTD",
    "CUSTO",
    "PERC",
    "ALIQ",
    "BASE",
    "SALDO",
    "PRECO",
)

INTEGER_NAMES = {
    "NUNOTA",
    "NUMNOTA",
    "NUFIN",
    "CODPROJ",
    "CODPARC",
    "CODTIPOPER",
    "CODTIPVENDA",
    "CODEMP",
    "SEQUENCIA",
    "CODPROD",
    "NUBCO",
}


def normalize_rows(
    rows: list[dict[str, Any]],
) -> pl.DataFrame:
    if not rows:
        return pl.DataFrame()

    normalized_rows = [
        {
            str(key).lower(): value
            for key, value in row.items()
        }
        for row in rows
    ]

    frame = pl.DataFrame(
        normalized_rows,
        infer_schema_length=None,
    )

    expressions: list[pl.Expr] = []

    for column in frame.columns:
        upper = column.upper()
        source = pl.col(column)

        if upper in INTEGER_NAMES:
            expressions.append(
                source
                .cast(pl.Int64, strict=False)
                .alias(column)
            )
            continue

        if any(hint in upper for hint in NUMERIC_HINTS):
            expressions.append(
                source
                .cast(pl.Float64, strict=False)
                .round(2)
                .alias(column)
            )
            continue

        if upper.startswith(DATE_HINTS) or upper.endswith("DATA"):
            text = source.cast(pl.String)

            expressions.append(
                pl.coalesce(
                    text.str.strptime(
                        pl.Datetime,
                        "%d/%m/%Y %H:%M:%S",
                        strict=False,
                    ),
                    text.str.strptime(
                        pl.Datetime,
                        "%d/%m/%Y %H:%M",
                        strict=False,
                    ),
                    text.str.strptime(
                        pl.Datetime,
                        "%Y-%m-%dT%H:%M:%S",
                        strict=False,
                    ),
                    text.str.strptime(
                        pl.Datetime,
                        "%Y-%m-%d %H:%M:%S",
                        strict=False,
                    ),
                    text.str.strptime(
                        pl.Date,
                        "%d/%m/%Y",
                        strict=False,
                    ).cast(pl.Datetime),
                    text.str.strptime(
                        pl.Date,
                        "%Y-%m-%d",
                        strict=False,
                    ).cast(pl.Datetime),
                ).alias(column)
            )

    if not expressions:
        return frame

    return frame.with_columns(expressions)


def frame_to_json_records(
    frame: pl.DataFrame,
) -> list[dict[str, Any]]:
    return frame.to_dicts()