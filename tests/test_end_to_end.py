from uuid import uuid4

from fastapi.testclient import TestClient

from app.schemas import AnalysisOutput
from app.services.dify import DifyError
from app.services.feishu import FeishuError
from tests.conftest import REQUEST_ID


def test_all_ten_scenarios_complete_through_public_api(full_mock_stack):
    app, scenarios, feishu, dify = full_mock_stack

    with TestClient(app) as client:
        for scenario in scenarios.all():
            request_id = str(uuid4())
            response = client.post(
                "/api/analyze",
                json={"scenario_id": scenario.id, "request_id": request_id},
            )

            assert response.status_code == 200
            payload = response.json()
            assert payload["status"] == "completed"
            assert payload["request_id"] == request_id
            analysis = AnalysisOutput.model_validate(payload["analysis"])
            assert [item.day for item in analysis.seven_day_actions] == list(range(1, 8))
            assert feishu.records[request_id].status == "completed"

    assert len(scenarios.all()) == 10
    assert feishu.create_count == 10
    assert len(dify.calls) == 10


def test_dify_timeout_retry_reuses_the_original_record(full_mock_stack):
    app, scenarios, feishu, dify = full_mock_stack
    scenario = scenarios.all()[0]
    dify.error = DifyError("dify_timeout")

    with TestClient(app) as client:
        failed = client.post(
            "/api/analyze", json={"scenario_id": scenario.id, "request_id": REQUEST_ID}
        )
        original_record = feishu.records[REQUEST_ID]
        dify.error = None
        retried = client.post(
            "/api/retry", json={"scenario_id": scenario.id, "request_id": REQUEST_ID}
        )

    assert failed.status_code == 200
    assert failed.json()["status"] == "retryable_failed"
    assert failed.json()["error_code"] == "dify_timeout"
    assert retried.status_code == 200
    assert retried.json()["status"] == "completed"
    assert feishu.create_count == 1
    assert feishu.records[REQUEST_ID].record_id == original_record.record_id
    assert feishu.records[REQUEST_ID].status == "completed"
    assert len(dify.calls) == 2


def test_invalid_dify_output_is_retryable_without_creating_another_row(full_mock_stack):
    app, scenarios, feishu, dify = full_mock_stack
    scenario = scenarios.all()[0]
    dify.error = DifyError("dify_invalid_output")

    with TestClient(app) as client:
        response = client.post(
            "/api/analyze", json={"scenario_id": scenario.id, "request_id": REQUEST_ID}
        )

    assert response.status_code == 200
    assert response.json()["status"] == "retryable_failed"
    assert response.json()["error_code"] == "dify_invalid_output"
    assert feishu.create_count == 1
    assert feishu.records[REQUEST_ID].status == "retryable_failed"


def test_feishu_auth_401_stops_before_ai_and_returns_safe_error(full_mock_stack):
    app, scenarios, feishu, dify = full_mock_stack
    feishu.fail_next("token", "feishu_auth_failed")
    scenario = scenarios.all()[0]

    with TestClient(app) as client:
        response = client.post(
            "/api/analyze",
            json={"scenario_id": scenario.id, "request_id": str(uuid4())},
        )

    assert response.status_code == 503
    assert response.json() == {"detail": {"code": "feishu_auth_failed"}}
    assert feishu.create_count == 0
    assert dify.calls == []


def test_feishu_write_429_can_recover_on_same_request_id(full_mock_stack):
    app, scenarios, feishu, dify = full_mock_stack
    scenario = scenarios.all()[0]
    feishu.fail_next("update", "feishu_update_failed")

    with TestClient(app) as client:
        first = client.post(
            "/api/analyze", json={"scenario_id": scenario.id, "request_id": REQUEST_ID}
        )
        record_id = feishu.records[REQUEST_ID].record_id
        second = client.post(
            "/api/retry", json={"scenario_id": scenario.id, "request_id": REQUEST_ID}
        )

    assert first.status_code == 503
    assert first.json() == {"detail": {"code": "feishu_update_failed"}}
    assert second.status_code == 200
    assert second.json()["status"] == "completed"
    assert feishu.create_count == 1
    assert feishu.records[REQUEST_ID].record_id == record_id
    assert feishu.records[REQUEST_ID].status == "completed"
    assert len(dify.calls) == 2


def test_invalid_sample_id_never_reaches_feishu_or_dify(full_mock_stack):
    app, _, feishu, dify = full_mock_stack

    with TestClient(app) as client:
        response = client.post(
            "/api/analyze", json={"scenario_id": "not-a-sample", "request_id": str(uuid4())}
        )

    assert response.status_code == 400
    assert response.json() == {"detail": {"code": "unknown_scenario"}}
    assert feishu.events == []
    assert dify.calls == []
