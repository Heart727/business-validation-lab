import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.config import Settings
from app.schemas import AnalysisOutput, DayAction


CONFIG_KEYS = (
    "DEMO_MODE", "FEISHU_APP_ID", "FEISHU_APP_SECRET", "FEISHU_APP_TOKEN",
    "FEISHU_TABLE_ID", "DIFY_BASE_URL", "DIFY_WORKFLOW_API_KEY",
)


@pytest.fixture
def isolated_config(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    for key in CONFIG_KEYS:
        monkeypatch.delenv(key, raising=False)


def valid_output():
    return {
        "executive_summary": "虚构样例的离线分析预览",
        "observations": [
            "证据：输入明确提供了虚构样例数据。",
            "推断：当前问题可能与客户触达方式有关，需要验证。",
            "缺失信息：尚无按渠道拆分的询单基线。",
        ],
        "risks": [],
        "seven_day_actions": [
            {"day": day, "action": "记录需求", "metric": "询单数", "decision_rule": "若无询单则调整展示"}
            for day in range(1, 8)
        ],
    }


def test_valid_analysis_has_exactly_seven_distinct_days():
    result = AnalysisOutput.model_validate(valid_output())
    assert [item.day for item in result.seven_day_actions] == list(range(1, 8))


@pytest.mark.parametrize("count", [6, 8])
def test_wrong_action_count_is_rejected(count):
    payload = valid_output()
    payload["seven_day_actions"] = payload["seven_day_actions"][:count]
    if count == 8:
        payload["seven_day_actions"].append({**payload["seven_day_actions"][0], "day": 8})
    with pytest.raises(ValidationError):
        AnalysisOutput.model_validate(payload)


def test_duplicate_day_is_rejected():
    payload = valid_output()
    payload["seven_day_actions"][6]["day"] = 1
    with pytest.raises(ValidationError, match="days 1 through 7 once"):
        AnalysisOutput.model_validate(payload)


@pytest.mark.parametrize("removed_label", ["证据", "推断", "缺失信息"])
def test_observations_require_evidence_inference_and_missing_information(removed_label):
    payload = valid_output()
    payload["observations"] = [
        item for item in payload["observations"]
        if not item.startswith(f"{removed_label}：")
    ]
    with pytest.raises(ValidationError, match="evidence, inference, and missing information"):
        AnalysisOutput.model_validate(payload)


@pytest.mark.parametrize("day", [0, 8])
def test_action_day_outside_week_is_rejected(day):
    with pytest.raises(ValidationError):
        DayAction(day=day, action="记录需求", metric="询单数", decision_rule="低于阈值则调整")


def test_output_rejects_unknown_fields_and_empty_summary():
    payload = valid_output()
    with pytest.raises(ValidationError):
        AnalysisOutput.model_validate({**payload, "unexpected": "value"})
    with pytest.raises(ValidationError):
        AnalysisOutput.model_validate({**payload, "executive_summary": ""})


def test_offline_preview_is_labeled_and_valid():
    preview = json.loads(Path("data/example_analysis.json").read_text(encoding="utf-8"))
    assert preview["preview_label"] == "虚构样例｜离线预览，非实时 AI 结果"
    AnalysisOutput.model_validate(preview["analysis"])


def test_live_mode_defaults_off_and_requires_all_credentials(settings, isolated_config):
    assert Settings.from_env().demo_mode is False
    assert settings.live_demo_ready is False
    assert Settings(demo_mode=True).live_demo_ready is False
    assert Settings(demo_mode=True, feishu_app_id="test", feishu_app_secret="test",
                    feishu_app_token="test", feishu_table_id="test",
                    dify_workflow_api_key="test").live_demo_ready is True


def test_settings_loads_dotenv_without_echoing_secrets(tmp_path, isolated_config):
    secret = "fictional-secret-for-test"
    (tmp_path / ".env").write_text(f"DEMO_MODE=true\nFEISHU_APP_SECRET={secret}\n", encoding="utf-8")
    settings = Settings.from_env()
    assert settings.demo_mode is True
    assert settings.feishu_app_secret == secret
    assert settings.live_demo_ready is False
    assert secret not in repr(settings)
