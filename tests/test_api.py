import json
from pathlib import Path
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.schemas import AnalysisOutput, PipelineResult
from app.services.pipeline import PipelineError
from app.services.scenarios import ScenarioCatalog
from tests.conftest import REQUEST_ID
from tests.test_schemas import valid_output


class FakePipeline:
    def __init__(self):
        self.calls = []
        self.error = None
        self.result = PipelineResult(
            request_id=REQUEST_ID,
            status="completed",
            analysis=AnalysisOutput.model_validate(valid_output()),
        )

    async def submit(self, scenario_id, request_id):
        self.calls.append((scenario_id, request_id))
        if self.error is not None:
            raise self.error
        return self.result.model_copy(update={"request_id": request_id})


@pytest.fixture
def api_parts(settings):
    scenarios = ScenarioCatalog.load(Path("data/scenarios.json"))
    pipeline = FakePipeline()
    app = build_app(settings, pipeline, scenarios)
    return app, settings, pipeline, scenarios


def build_app(settings: Settings, pipeline: FakePipeline, scenarios: ScenarioCatalog):
    from app.main import create_app

    return create_app(settings=settings, pipeline=pipeline, scenarios=scenarios)


def test_health_and_scenario_list_are_public_safe(api_parts):
    app, settings, _, scenarios = api_parts
    with TestClient(app) as client:
        health = client.get("/api/health")
        listing = client.get("/api/scenarios")

    assert health.json() == {"status": "ok", "live_demo_enabled": settings.live_demo_ready}
    assert listing.json() == [
        scenario.model_dump() for scenario in scenarios.all()
    ]
    assert len(listing.json()) == 10
    assert settings.feishu_app_secret not in health.text + listing.text


def test_preview_returns_only_validated_static_analysis(api_parts):
    app, _, _, _ = api_parts
    expected = json.loads(Path("data/example_analysis.json").read_text(encoding="utf-8"))["analysis"]

    with TestClient(app) as client:
        response = client.get("/api/preview")

    assert response.status_code == 200
    assert response.json() == expected


def test_live_submission_is_disabled_without_all_configuration(api_parts):
    app, _, pipeline, scenarios = api_parts
    scenario_id = scenarios.all()[0].id

    with TestClient(app) as client:
        response = client.post(
            "/api/analyze", json={"scenario_id": scenario_id, "request_id": REQUEST_ID}
        )

    assert response.status_code == 503
    assert response.json() == {"detail": {"code": "demo_disabled"}}
    assert pipeline.calls == []


def test_live_submission_uses_fixed_scenario_and_serializes_result(api_parts):
    _, settings, pipeline, scenarios = api_parts
    app = build_app(settings.model_copy(update={"demo_mode": True}), pipeline, scenarios)
    scenario_id = scenarios.all()[0].id

    with TestClient(app) as client:
        response = client.post(
            "/api/analyze", json={"scenario_id": scenario_id, "request_id": REQUEST_ID}
        )

    assert response.status_code == 200
    assert response.json() == pipeline.result.model_dump(mode="json")
    assert pipeline.calls == [(scenario_id, str(UUID(REQUEST_ID)))]


def test_retry_forwards_the_same_request_id(api_parts):
    _, settings, pipeline, scenarios = api_parts
    app = build_app(settings.model_copy(update={"demo_mode": True}), pipeline, scenarios)
    scenario_id = scenarios.all()[0].id

    with TestClient(app) as client:
        response = client.post(
            "/api/retry", json={"scenario_id": scenario_id, "request_id": REQUEST_ID}
        )

    assert response.status_code == 200
    assert pipeline.calls == [(scenario_id, str(UUID(REQUEST_ID)))]


def test_invalid_scenario_is_rejected_before_pipeline_call(api_parts):
    _, settings, pipeline, scenarios = api_parts
    app = build_app(settings.model_copy(update={"demo_mode": True}), pipeline, scenarios)

    with TestClient(app) as client:
        response = client.post(
            "/api/analyze", json={"scenario_id": "arbitrary", "request_id": REQUEST_ID}
        )

    assert response.status_code == 400
    assert response.json() == {"detail": {"code": "unknown_scenario"}}
    assert pipeline.calls == []


@pytest.mark.parametrize(
    "body",
    [
        {"scenario_id": "valid", "request_id": "not-a-uuid"},
        {"scenario_id": "valid", "request_id": REQUEST_ID, "contact": "person@example.test"},
    ],
)
def test_request_rejects_bad_id_and_arbitrary_personal_fields(api_parts, body):
    _, settings, pipeline, scenarios = api_parts
    app = build_app(settings.model_copy(update={"demo_mode": True}), pipeline, scenarios)
    body["scenario_id"] = scenarios.all()[0].id

    with TestClient(app) as client:
        response = client.post("/api/analyze", json=body)

    assert response.status_code == 422
    assert pipeline.calls == []


@pytest.mark.parametrize(
    "error,status,public_code",
    [
        (PipelineError("feishu_lookup_failed"), 503, "feishu_lookup_failed"),
        (PipelineError("feishu_duplicate_request_id"), 409, "feishu_duplicate_request_id"),
        (PipelineError("private upstream body: secret"), 503, "service_unavailable"),
    ],
)
def test_pipeline_errors_are_mapped_to_sanitized_http_responses(
    api_parts, error, status, public_code
):
    _, settings, pipeline, scenarios = api_parts
    app = build_app(settings.model_copy(update={"demo_mode": True}), pipeline, scenarios)
    pipeline.error = error
    scenario_id = scenarios.all()[0].id

    with TestClient(app) as client:
        response = client.post(
            "/api/analyze", json={"scenario_id": scenario_id, "request_id": REQUEST_ID}
        )

    assert response.status_code == status
    assert response.json() == {"detail": {"code": public_code}}
    assert "private upstream body" not in response.text
    assert "secret" not in response.text
