from decimal import Decimal
from typing import Any

import polars as pl


def create_frame(
    rows: list[dict[str, Any]],
) -> pl.DataFrame:
    if not rows:
        return pl.DataFrame()

    return pl.DataFrame(
        rows,
        infer_schema_length=None,
    )


def sum_column(
    frame: pl.DataFrame,
    column: str,
) -> Decimal:
    if frame.is_empty():
        return Decimal("0")

    if column not in frame.columns:
        return Decimal("0")

    values = frame.get_column(column).to_list()

    return sum(
        (
            Decimal(str(value))
            for value in values
            if value is not None
        ),
        Decimal("0"),
    )


def to_float(
    value: Decimal,
) -> float:
    return float(
        value.quantize(
            Decimal("0.01")
        )
    )