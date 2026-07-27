"""Calcul deterministe des annees d'experience (app.core.experience)."""

from __future__ import annotations

from datetime import date

from app.core.experience import format_years, years_from_periods


def test_single_full_year():
    # 2020-01 a 2020-12 inclus = 12 mois = 1.0 an.
    assert years_from_periods([{"start": "2020-01", "end": "2020-12"}]) == 1.0


def test_internship_excluded():
    periods = [
        {"start": "2020-01", "end": "2020-12"},
        {"start": "2019-01", "end": "2019-12", "internship": True},
    ]
    assert years_from_periods(periods) == 1.0


def test_overlap_not_double_counted():
    # P1 2020-01..2020-12 et P2 2020-06..2021-05 -> union 2020-01..2021-05.
    periods = [
        {"start": "2020-01", "end": "2020-12"},
        {"start": "2020-06", "end": "2021-05"},
    ]
    # Union = 17 mois (pas 24) -> 1.4 ; et NON 2.0 si on doublait.
    assert years_from_periods(periods) == 1.4


def test_present_uses_today():
    # 2020-01 -> present, "aujourd'hui" = 2021-01 : 13 mois inclus = 1.1.
    out = years_from_periods(
        [{"start": "2020-01", "end": "present"}], today=date(2021, 1, 1)
    )
    assert out == 1.1


def test_deterministic_same_input_same_output():
    periods = [
        {"start": "2018-09", "end": "2021-03"},
        {"start": "2021-04", "end": "present"},
    ]
    a = years_from_periods(periods, today=date(2024, 1, 1))
    b = years_from_periods(periods, today=date(2024, 1, 1))
    assert a == b and a is not None


def test_none_when_no_usable_period():
    assert years_from_periods([]) is None
    assert years_from_periods([{"start": "stage", "end": "?"}]) is None
    assert years_from_periods([{"start": "2020", "internship": True}]) is None


def test_format_years_drops_trailing_zero():
    assert format_years(5.0) == "5"
    assert format_years(4.5) == "4.5"
