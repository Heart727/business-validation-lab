from typing import Literal

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
        present = set()
        for observation in self.observations:
            text = observation.lstrip()
            for label in _OBSERVATION_LABELS:
                prefix = next(
                    (candidate for candidate in (f"{label}：", f"{label}:") if text.startswith(candidate)),
                    None,
                )
                if prefix and text[len(prefix):].strip():
                    present.add(label)
        if present != _OBSERVATION_LABELS:
            raise ValueError("observations must separate evidence, inference, and missing information")
        return self


class PipelineResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str = Field(min_length=1)
    status: Literal["processing", "completed", "retryable_failed"]
    analysis: AnalysisOutput | None = None
    error_code: str | None = None

    @model_validator(mode="after")
    def validate_state_payload(self):
        if self.status == "completed" and (self.analysis is None or self.error_code is not None):
            raise ValueError("completed results require analysis and cannot contain an error")
        if self.status == "retryable_failed" and (
            self.analysis is not None or not self.error_code
        ):
            raise ValueError("retryable failures require an error code and cannot contain analysis")
        if self.status == "processing" and (self.analysis is not None or self.error_code is not None):
            raise ValueError("processing results cannot contain analysis or an error")
        return self
