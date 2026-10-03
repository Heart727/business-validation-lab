import json
import traceback

import httpx
import pytest
import pytest_asyncio

from app.schemas import AnalysisOutput
from app.services.dify import DifyClient, DifyError
from tests.conftest import REQUEST_ID
from tests.test_schemas import valid_output


def blocking_response(output=None):
    return httpx.Response(200, json={
        "data": {"status": "succeeded", "outputs": {
            "analysis_json": json.dumps(valid_output() if output is None else output)
        }}
    })


@pytest_asyncio.fixture
async def dify_client(settings):
    async with httpx.AsyncClient(transport=httpx.MockTransport(
        lambda request: blocking_response()
    )) as http_client:
        yield DifyClient(settings, http_client)


@pytest.mark.asyncio
async def test_run_workflow_validates_analysis_json(dify_client, scenario):
    result = await dify_client.run_workflow(scenario, REQUEST_ID)
    assert isinstance(result, AnalysisOutput)
    assert [item.day for item in result.seven_day_actions] == list(range(1, 8))


@pytest.mark.asyncio
async def test_posts_only_scenario_with_server_key_and_timeout(settings, scenario):
    settings = settings.model_copy(update={
        "dify_base_url": "https://dify.example/v1/", "dify_workflow_api_key": "server-only-test-key",
    })

    def handler(request):
        assert request.method == "POST"
        assert str(request.url) == "https://dify.example/v1/workflows/run"
        assert request.headers["Authorization"] == "Bearer server-only-test-key"
        assert request.extensions["timeout"] == dict.fromkeys(("connect", "read", "write", "pool"), 30.0)
        assert json.loads(request.content) == {
            "response_mode": "blocking", "user": REQUEST_ID,
            "inputs": {"scenario_json": scenario.model_dump_json()},
        }
        return blocking_response()

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        await DifyClient(settings, http_client).run_workflow(scenario, REQUEST_ID)


@pytest.mark.asyncio
@pytest.mark.parametrize("status,code", [
    (401, "dify_upstream_failed"), (429, "dify_quota_rejected"),
    (500, "dify_upstream_failed"), (302, "dify_upstream_failed"),
])
async def test_http_failures_are_safe_codes(settings, scenario, status, code):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(status, headers={"Location": "https://attacker.example/steal"},
                              text="sensitive-upstream-body")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler), follow_redirects=True) as http_client:
        with pytest.raises(DifyError) as caught:
            await DifyClient(settings, http_client).run_workflow(scenario, REQUEST_ID)
    assert caught.value.code == code
    assert len(calls) == 1
    assert caught.value.__cause__ is None
    rendered = "".join(traceback.format_exception(caught.value))
    assert "test-workflow-key" not in rendered
    assert "sensitive-upstream-body" not in rendered


@pytest.mark.asyncio
@pytest.mark.parametrize("failure,code", [
    ("timeout", "dify_timeout"), ("connection", "dify_upstream_failed"),
])
async def test_transport_failures_are_safe_codes(settings, scenario, failure, code):
    def handler(request):
        if failure == "timeout":
            raise httpx.ReadTimeout("test-workflow-key sensitive-upstream-body", request=request)
        raise httpx.ConnectError("test-workflow-key sensitive-upstream-body", request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        with pytest.raises(DifyError) as caught:
            await DifyClient(settings, http_client).run_workflow(scenario, REQUEST_ID)
    assert caught.value.code == code
    assert caught.value.__cause__ is None
    rendered = "".join(traceback.format_exception(caught.value))
    assert "test-workflow-key" not in rendered
    assert "sensitive-upstream-body" not in rendered


@pytest.mark.asyncio
@pytest.mark.parametrize("response", [
    httpx.Response(200, text="sensitive-upstream-body"),
    httpx.Response(200, json={"data": {"outputs": {}}}),
    httpx.Response(200, json={"data": {"status": "failed", "outputs": {"analysis_json": "{}"}}}),
    httpx.Response(200, json={"data": {"outputs": {"analysis_json": {}}}}),
])
async def test_malformed_blocking_response_is_invalid_output(settings, scenario, response):
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request: response)) as http_client:
        with pytest.raises(DifyError, match="^dify_invalid_output$"):
            await DifyClient(settings, http_client).run_workflow(scenario, REQUEST_ID)


@pytest.mark.asyncio
async def test_six_actions_are_invalid_output(settings, scenario):
    output = valid_output()
    output["seven_day_actions"] = output["seven_day_actions"][:6]
    async with httpx.AsyncClient(transport=httpx.MockTransport(
        lambda request: blocking_response(output)
    )) as http_client:
        with pytest.raises(DifyError, match="^dify_invalid_output$") as caught:
            await DifyClient(settings, http_client).run_workflow(scenario, REQUEST_ID)
    assert caught.value.__cause__ is None


@pytest.mark.asyncio
async def test_missing_server_key_makes_no_request(settings, scenario):
    async with httpx.AsyncClient(transport=httpx.MockTransport(
        lambda request: pytest.fail("No request expected without server key")
    )) as http_client:
        with pytest.raises(DifyError, match="^dify_upstream_failed$"):
            await DifyClient(settings.model_copy(update={"dify_workflow_api_key": None}), http_client).run_workflow(
                scenario, REQUEST_ID
            )
