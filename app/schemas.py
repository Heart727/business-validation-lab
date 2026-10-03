from pydantic import BaseModel, ConfigDict, Field, model_validator


_OBSERVATION_LABELS = frozenset({"证据", "推断", "缺失信息"})


class Scenario(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    title: str
    industry: str
    offering: str
    target_customer: str
    business_problem: str
    current_metrics: str
    budget_range: str
    goal: str
    time_limit: str


class DayAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    day: int = Field(ge=1, le=7)
    action: str = Field(min_length=1)
    metric: str = Field(min_length=1)
    decision_rule: str = Field(min_length=1)


class AnalysisOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    executive_summary: str = Field(min_length=1, max_length=1200)
    observations: list[str] = Field(min_length=1, max_length=8)
    risks: list[str] = Field(max_length=8)
    seven_day_actions: list[DayAction] = Field(min_length=7, max_length=7)

    @model_validator(mode="after")
    def require_seven_distinct_days(self):
        if sorted(item.day for item in self.seven_day_actions) != list(range(1, 8)):
            raise ValueError("seven_day_actions must contain days 1 through 7 once")
        return self

    @model_validator(mode="after")
    def require_separated_observations(self):
        present = {
            label
            for observation in self.observations
            for label in _OBSERVATION_LABELS
            if observation.lstrip().startswith((f"{label}：", f"{label}:"))
        }
        if present != _OBSERVATION_LABELS:
            raise ValueError("observations must separate evidence, inference, and missing information")
        return self
