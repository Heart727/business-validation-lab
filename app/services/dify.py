"""Blocking Dify workflow client with application-safe failures."""

import httpx
from pydantic import ValidationError

from app.config import Settings
from app.schemas import AnalysisOutput, Scenario


class DifyError(Exception):
    """A stable, safe failure code for the workflow boundary."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class DifyClient:
    def __init__(self, settings: Settings, http_client: httpx.AsyncClient) -> None:
        self.settings = settings
        self.http_client = http_client

    async def run_workflow(self, scenario: Scenario, request_id: str) -> AnalysisOutput:
        api_key = self.settings.dify_workflow_api_key
        if not api_key:
            raise DifyError("dify_upstream_failed")

        try:
            response = await self.http_client.post(
                f"{self.settings.dify_base_url.rstrip('/')}/workflows/run",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "response_mode": "blocking",
                    "user": request_id,
                    "inputs": {"scenario_json": scenario.model_dump_json()},
                },
                timeout=30.0,
                follow_redirects=False,
            )
        except httpx.TimeoutException:
            raise DifyError("dify_timeout") from None
        except httpx.RequestError:
            raise DifyError("dify_upstream_failed") from None

        if response.status_code == 429:
            raise DifyError("dify_quota_rejected")
        if not 200 <= response.status_code < 300:
            raise DifyError("dify_upstream_failed")

        try:
            payload = response.json()
            data = payload["data"]
            if data.get("status") != "succeeded":
                raise ValueError("Workflow did not succeed")
            analysis_json = data["outputs"]["analysis_json"]
            if not isinstance(analysis_json, str):
                raise ValueError("Invalid analysis output type")
            return AnalysisOutput.model_validate_json(analysis_json)
        except (ValueError, TypeError, KeyError, AttributeError, ValidationError):
            raise DifyError("dify_invalid_output") from None
