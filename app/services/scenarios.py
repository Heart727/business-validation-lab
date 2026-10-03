import json
from pathlib import Path

from app.schemas import Scenario


class UnknownScenario(LookupError):
    """The requested scenario ID is absent from the fixed catalog."""


class ScenarioCatalog:
    def __init__(self, scenarios: list[Scenario]):
        by_id = {scenario.id: scenario for scenario in scenarios}
        if len(by_id) != len(scenarios):
            raise ValueError("duplicate scenario id")
        self._scenarios = tuple(scenarios)
        self._by_id = by_id

    @classmethod
    def load(cls, path: Path) -> "ScenarioCatalog":
        records = json.loads(path.read_text(encoding="utf-8"))
        return cls([Scenario.model_validate(record) for record in records])

    def get(self, scenario_id: str) -> Scenario:
        try:
            return self._by_id[scenario_id]
        except KeyError as exc:
            raise UnknownScenario(scenario_id) from exc

    def all(self) -> list[Scenario]:
        return list(self._scenarios)
