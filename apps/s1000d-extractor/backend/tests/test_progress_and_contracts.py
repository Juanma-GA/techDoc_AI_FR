from app.core.ir import RawBlock
from app.core.progress import scaled_progress
from app.core.structure_infer import build_ir


def test_inference_reports_completed_blocks() -> None:
    blocks = [RawBlock(text=f"Source paragraph {index}.", page=1) for index in range(30)]
    notifications = []
    root = build_ir(blocks, progress_cb=lambda done, total: notifications.append((done, total)))
    assert root.children
    assert notifications[-1][0] == notifications[-1][1]
    assert [done for done, _total in notifications] == list(range(1, len(notifications) + 1))


def test_scaled_progress_reports_real_percentages_without_repeated_events() -> None:
    events = []
    report = scaled_progress(lambda step, pct: events.append((step, pct)), "infer", 40, 55)
    for completed in range(1, 1001):
        report(completed, 1000)
    assert events == [("infer", pct) for pct in range(41, 56)]


def test_openapi_exposes_typed_responses_without_reading_data(app) -> None:
    schema = app.openapi()
    assert "WizardStateOut" in schema["components"]["schemas"]
    assert "DmValidationResultOut" in schema["components"]["schemas"]
    assert "PreliminaryStateOut" in schema["components"]["schemas"]
    for endpoint in [
        "/api/v1/documents/{doc_id}/wizard/start",
        "/api/v1/validation/dms",
        "/api/v1/documents/{doc_id}/resources/{kind}",
    ]:
        response = schema["paths"][endpoint]["post"]["responses"]["200"]["content"]["application/json"][
            "schema"
        ]
        assert "$ref" in response
