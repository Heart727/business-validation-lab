"""Blocking Dify workflow client with application-safe failures."""

import asyncio

import httpx
from pydantic import ValidationError

from app.config import Settings
from app.schemas import AnalysisOutput, Scenario


DIFY_REQUEST_TIMEOUT_SECONDS = 30.0


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
            async with asyncio.timeout(DIFY_REQUEST_TIMEOUT_SECONDS):
                response = await self.http_client.post(
                    f"{self.settings.dify_base_url.rstrip('/')}/workflows/run",
                    headers={"Authorization": f"Bearer {api_key}"},
                    json={
                        "response_mode": "blocking",
                        "user": request_id,
                        "inputs": {"scenario_json": scenario.model_dump_json()},
                    },
                    timeout=DIFY_REQUEST_TIMEOUT_SECONDS,
                    follow_redirects=False,
                )
        except TimeoutError:
            raise DifyError("dify_timeout") from None
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
            status = data.get("status")
            if not isinstance(status, str):
                raise ValueError("Missing workflow status")
            if status != "succeeded":
                raise DifyError("dify_upstream_failed")
            analysis_json = data["outputs"]["analysis_json"]
            if not isinstance(analysis_json, str):
                raise ValueError("Invalid analysis output type")
            return AnalysisOutput.model_validate_json(analysis_json)
        except (ValueError, TypeError, KeyError, AttributeError, ValidationError):
            raise DifyError("dify_invalid_output") from None
