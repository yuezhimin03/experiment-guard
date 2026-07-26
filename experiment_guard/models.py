from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class MetricResult:
    name: str
    kind: str
    control: float
    treatment: float
    absolute: float
    relative: float | None
    p_value: float
    ci_low: float
    ci_high: float
    passed: bool | None = None
    note: str = ""


@dataclass(frozen=True)
class GuardrailResult:
    name: str
    control: float
    treatment: float
    absolute: float
    margin: float
    passed: bool
    p_value: float
    rule: str


@dataclass(frozen=True)
class ExperimentResult:
    experiment_name: str
    control_users: int
    treatment_users: int
    srm_chi_square: float
    srm_p_value: float
    srm_passed: bool
    primary: MetricResult
    secondary: tuple[MetricResult, ...]
    guardrails: tuple[GuardrailResult, ...]
    cuped_theta: float
    cuped_variance_reduction: float
    cuped_metric: MetricResult
    planned_users_per_group: int
    information_fraction: float
    sequential_p_threshold: float
    decision: str
    reasons: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

