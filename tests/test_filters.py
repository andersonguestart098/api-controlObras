from datetime import date

import pytest
from pydantic import ValidationError

from app.schemas.filters import DashboardFilters


def test_valid_filters() -> None:
    filters = DashboardFilters(
        codproj=20000000,
        dtneg_inicial=date(2026, 1, 1),
        dtneg_final=date(2026, 7, 21),
    )
    assert filters.codproj == 20000000


def test_invalid_period() -> None:
    with pytest.raises(ValidationError):
        DashboardFilters(
            codproj=20000000,
            dtneg_inicial=date(2026, 7, 21),
            dtneg_final=date(2026, 1, 1),
        )
