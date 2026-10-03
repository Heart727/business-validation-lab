"""Run all ten fixed samples through the API's pipeline without network calls."""

import asyncio
import sys
from pathlib import Path
from uuid import uuid4


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import Settings
from app.services.pipeline import PipelineService
from app.services.scenarios import ScenarioCatalog
from tests.fakes import DeterministicDify, InMemoryFeishu


async def verify_all_scenarios() -> list[str]:
    catalog = ScenarioCatalog.load(ROOT / "data" / "scenarios.json")
    feishu = InMemoryFeishu()
    dify = DeterministicDify()
    feishu.events = dify.events
    settings = Settings(
        demo_mode=True,
        feishu_app_id="mock-app-id",
        feishu_app_secret="mock-app-secret",
        feishu_app_token="mock-app-token",
        feishu_table_id="mock-table-id",
        dify_workflow_api_key="mock-workflow-key",
    )
    pipeline = PipelineService(feishu=feishu, dify=dify, scenarios=catalog)
    completed = []

    for scenario in catalog.all():
        request_id = str(uuid4())
        result = await pipeline.submit(scenario.id, request_id)
        if result.status != "completed" or result.analysis is None:
            raise AssertionError("sample did not complete")
        if [action.day for action in result.analysis.seven_day_actions] != list(range(1, 8)):
            raise AssertionError("sample did not return seven actions")
        if feishu.records[request_id].status != "completed":
            raise AssertionError("sample was not saved")
        completed.append(scenario.id)

    if len(completed) != 10 or feishu.create_count != 10 or len(dify.calls) != 10:
        raise AssertionError("sample count mismatch")
    return completed


def main() -> int:
    try:
        completed = asyncio.run(verify_all_scenarios())
    except Exception:
        return 1
    print(f"{len(completed)} scenarios passed")
    for scenario_id in completed:
        print(scenario_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
