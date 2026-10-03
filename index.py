"""Vercel Python runtime entry point."""

from pathlib import Path

import httpx

from app.config import Settings
from app.main import create_app
from app.services.dify import DifyClient
from app.services.feishu import FeishuClient
from app.services.pipeline import PipelineService
from app.services.scenarios import ScenarioCatalog


ROOT = Path(__file__).resolve().parent
settings = Settings.from_env()
scenarios = ScenarioCatalog.load(ROOT / "data" / "scenarios.json")
feishu_http = httpx.AsyncClient()
dify_http = httpx.AsyncClient()
pipeline = PipelineService(
    feishu=FeishuClient(settings, feishu_http),
    dify=DifyClient(settings, dify_http),
    scenarios=scenarios,
)
app = create_app(settings=settings, pipeline=pipeline, scenarios=scenarios)
