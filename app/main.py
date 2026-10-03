"""FastAPI routes for the fictional-scenario public demo."""

import json
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import ValidationError

from app.config import Settings
from app.schemas import AnalysisOutput, PipelineResult, ScenarioRequest
from app.services.pipeline import PipelineError, PipelineService
from app.services.scenarios import ScenarioCatalog, UnknownScenario


_PUBLIC_PIPELINE_CODES = frozenset({
    "feishu_auth_failed",
    "feishu_lookup_failed",
    "feishu_create_failed",
    "feishu_update_failed",
    "feishu_invalid_response",
    "feishu_duplicate_request_id",
    "pipeline_timeout",
})


def create_app(
    settings: Settings,
    pipeline: PipelineService,
    scenarios: ScenarioCatalog,
) -> FastAPI:
    app = FastAPI(title="AI 经营分析与 7 天验证助手", version="0.1.0")
    preview_path = Path(__file__).resolve().parent.parent / "data" / "example_analysis.json"
    try:
        preview_data = json.loads(preview_path.read_text(encoding="utf-8"))
        preview = AnalysisOutput.model_validate(preview_data["analysis"])
    except (OSError, ValueError, KeyError, TypeError, ValidationError):
        raise RuntimeError("Static analysis preview is invalid") from None

    @app.get("/api/health")
    async def health() -> dict[str, object]:
        return {"status": "ok", "live_demo_enabled": settings.live_demo_ready}

    @app.get("/api/scenarios")
    async def list_scenarios() -> list[dict[str, str]]:
        return [{"id": item.id, "title": item.title} for item in scenarios.all()]

    @app.get("/api/preview", response_model=AnalysisOutput)
    async def get_preview() -> AnalysisOutput:
        return preview

    async def submit(body: ScenarioRequest) -> PipelineResult:
        try:
            scenarios.get(body.scenario_id)
        except UnknownScenario:
            raise HTTPException(status_code=400, detail={"code": "unknown_scenario"}) from None

        if not settings.live_demo_ready:
            raise HTTPException(status_code=503, detail={"code": "demo_disabled"})

        try:
            return await pipeline.submit(body.scenario_id, str(body.request_id))
        except UnknownScenario:
            raise HTTPException(status_code=400, detail={"code": "unknown_scenario"}) from None
        except PipelineError as error:
            code = error.code if error.code in _PUBLIC_PIPELINE_CODES else "service_unavailable"
            status = {
                "feishu_duplicate_request_id": 409,
                "pipeline_timeout": 504,
            }.get(code, 503)
            raise HTTPException(status_code=status, detail={"code": code}) from None

    @app.post("/api/analyze", response_model=PipelineResult)
    async def analyze(body: ScenarioRequest) -> PipelineResult:
        return await submit(body)

    @app.post("/api/retry", response_model=PipelineResult)
    async def retry(body: ScenarioRequest) -> PipelineResult:
        return await submit(body)

    return app
