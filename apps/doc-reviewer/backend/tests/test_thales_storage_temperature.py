from __future__ import annotations

from types import SimpleNamespace

from app.checks.client_registry import load_active_client_configuration
from app.core.compiled_rule_executor import execute_pdf_rules
from app.parsers.pdf_parser import ParsedPage, ParsedPdf


_CLIENT_BUNDLE = load_active_client_configuration().bundle
_STORAGE_RULE = next(
    rule.compiled_rule
    for rule in _CLIENT_BUNDLE.rules
    if rule.code == "CUSTOM_STORAGE_NOTE"
)
_STORAGE_INTRODUCTION = (
    "NOTE: During storage operations, make sure that the environmental "
    "conditions are as follows:"
)
_RELATIVE_HUMIDITY = (
    "Relative humidity: Refer to Standard Practices Manual ATA No. 20-02-00, "
    "F9111CMON-A-20-02-00-00A-800A-A - Storage - General procedure."
)
_AIRBUS_TEMPERATURE = (
    "Temperature: Refer to Standard Practices Manual ATA No. 20-02-00, "
    "F9111CMON-A-20-02-00-00A-812A-A – Storage and Transportation of Assemblies."
)
_BOEING_TEMPERATURE = (
    "Temperature: Refer to SOPM 20-02-00 - STANDARD OVERHAUL PRACTICES MANUAL "
    "(SOPM), F9111CMON-A-20-02-00-00A-812A-A - Storage and Transportation of Assemblies."
)
_BOEING_HUMIDITY = (
    "Relative humidity: Refer to SOPM 20-02-00 - STANDARD OVERHAUL PRACTICES MANUAL "
    "(SOPM), F9111CMON-A-20-02-00-00A-800A-A - Storage - General procedure."
)


def _run_storage_rule(
    temperature: str,
    manufacturer: str,
    relative_humidity: str | None = None,
):
    if relative_humidity is None:
        relative_humidity = (
            _BOEING_HUMIDITY
            if manufacturer.strip().casefold() == "boeing"
            else _RELATIVE_HUMIDITY
        )
    text = (
        "STORAGE\n"
        f"{_STORAGE_INTRODUCTION}\n"
        "Pressure: 1 bar\n"
        f"{relative_humidity}\n"
        f"{temperature}"
    )
    page = ParsedPage(page=1, text=text, page_type="STORAGE")
    parsed = ParsedPdf(page_count=1, pages=[page], full_text=text, is_signed=False)
    return execute_pdf_rules(
        parsed,
        [_STORAGE_RULE],
        document=SimpleNamespace(meta_manufacturer=manufacturer),
        client_operations=_CLIENT_BUNDLE.operations,
    )


def test_storage_temperature_reference_is_specific_to_manufacturer() -> None:
    airbus_results, _ = _run_storage_rule(_AIRBUS_TEMPERATURE, "Airbus")
    boeing_results, _ = _run_storage_rule(_BOEING_TEMPERATURE, "Boeing")
    boeing_with_airbus_reference, _ = _run_storage_rule(
        _AIRBUS_TEMPERATURE, "Boeing"
    )
    airbus_with_boeing_reference, _ = _run_storage_rule(
        _BOEING_TEMPERATURE, "Airbus"
    )

    assert airbus_results[0].status == "PASS"
    assert boeing_results[0].status == "PASS"
    assert boeing_with_airbus_reference[0].status == "FAIL"
    assert airbus_with_boeing_reference[0].status == "FAIL"


def test_boeing_storage_temperature_suggestion_uses_sopm_reference() -> None:
    results, suggestions = _run_storage_rule(_AIRBUS_TEMPERATURE, "Boeing")

    assert results[0].status == "FAIL"
    assert len(suggestions) == 1
    assert suggestions[0].proposed == _BOEING_TEMPERATURE


def test_storage_humidity_reference_is_specific_to_manufacturer() -> None:
    airbus_results, _ = _run_storage_rule(_AIRBUS_TEMPERATURE, "Airbus")
    boeing_results, _ = _run_storage_rule(
        _BOEING_TEMPERATURE,
        "Boeing",
        relative_humidity=_BOEING_HUMIDITY,
    )
    boeing_with_airbus_reference, _ = _run_storage_rule(
        _BOEING_TEMPERATURE, "Boeing", relative_humidity=_RELATIVE_HUMIDITY
    )
    airbus_with_boeing_reference, _ = _run_storage_rule(
        _AIRBUS_TEMPERATURE, "Airbus", relative_humidity=_BOEING_HUMIDITY
    )

    assert airbus_results[0].status == "PASS"
    assert boeing_results[0].status == "PASS"
    assert boeing_with_airbus_reference[0].status == "FAIL"
    assert airbus_with_boeing_reference[0].status == "FAIL"


def test_boeing_storage_humidity_suggestion_uses_sopm_reference() -> None:
    results, suggestions = _run_storage_rule(
        _BOEING_TEMPERATURE, "Boeing", relative_humidity=_RELATIVE_HUMIDITY
    )

    assert results[0].status == "FAIL"
    assert len(suggestions) == 1
    assert suggestions[0].proposed == _BOEING_HUMIDITY
