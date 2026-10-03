import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.services.scenarios import ScenarioCatalog, UnknownScenario


def test_catalog_contains_ten_unique_fictional_scenarios():
    catalog = ScenarioCatalog.load(Path("data/scenarios.json"))
    scenarios = catalog.all()
    assert len(scenarios) == 10
    assert len({item.id for item in scenarios}) == 10
    forbidden = {"name", "phone", "email", "contact"}
    assert all(forbidden.isdisjoint(item.model_dump()) for item in scenarios)


def test_unknown_scenario_is_rejected():
    catalog = ScenarioCatalog.load(Path("data/scenarios.json"))
    with pytest.raises(UnknownScenario):
        catalog.get("not-a-scenario")


def test_catalog_returns_known_scenario_and_does_not_expose_mutable_state():
    catalog = ScenarioCatalog.load(Path("data/scenarios.json"))
    first = catalog.all()[0]
    assert catalog.get(first.id) == first
    with pytest.raises(ValidationError):
        first.title = "changed"
    catalog.all().clear()
    assert len(catalog.all()) == 10


def test_scenario_rejects_unexpected_input(scenario):
    with pytest.raises(ValidationError):
        type(scenario).model_validate({**scenario.model_dump(), "contact": "fake"})


def test_catalog_rejects_duplicate_ids(tmp_path):
    source = Path("data/scenarios.json").read_text(encoding="utf-8")
    records = json.loads(source)
    records[1]["id"] = records[0]["id"]
    path = tmp_path / "scenarios.json"
    path.write_text(json.dumps(records), encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate"):
        ScenarioCatalog.load(path)
