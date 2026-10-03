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
def scenario():
    from app.services.scenarios import ScenarioCatalog

    return ScenarioCatalog.load(Path("data/scenarios.json")).all()[0]
