from pathlib import Path

import pytest


REQUEST_ID = "0e9dbe92-0fc0-4cc2-9b5e-d7baccc04853"


@pytest.fixture
def settings():
    from app.config import Settings

    return Settings(
        demo_mode=False,
        feishu_app_id="test-app-id",
        feishu_app_secret="test-app-secret",
        feishu_app_token="test-app-token",
        feishu_table_id="test-table-id",
        dify_workflow_api_key="test-workflow-key",
    )


@pytest.fixture
def scenario(scenario_catalog):
    return scenario_catalog.all()[0]


@pytest.fixture
def scenario_catalog():
    from app.services.scenarios import ScenarioCatalog

    return ScenarioCatalog.load(Path(__file__).resolve().parents[1] / "data" / "scenarios.json")


@pytest.fixture
def full_mock_stack(settings, scenario_catalog):
    from app.main import create_app
    from app.services.pipeline import PipelineService
    from tests.fakes import DeterministicDify, InMemoryFeishu

    feishu = InMemoryFeishu()
    dify = DeterministicDify()
    feishu.events = dify.events
    pipeline = PipelineService(feishu=feishu, dify=dify, scenarios=scenario_catalog)
    app = create_app(
        settings=settings.model_copy(update={"demo_mode": True}),
        pipeline=pipeline,
        scenarios=scenario_catalog,
    )
    return app, scenario_catalog, feishu, dify
