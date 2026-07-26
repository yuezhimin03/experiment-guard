from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from .models import ExperimentResult, GuardrailResult, MetricResult
from .stats import (
    cuped_adjust,
    difference_in_means,
    difference_in_proportions,
    obrien_fleming_threshold,
    required_sample_size_for_proportion,
    srm_test,
)


REQUIRED_COLUMNS = {
    "user_id",
    "variant",
    "d7_retained",
    "payer",
    "revenue",
    "playtime_minutes",
    "pre_playtime_minutes",
    "crashed",
    "session_count",
}


@dataclass(frozen=True)
class UserMetric:
    user_id: str
    variant: str
    d7_retained: int
    payer: int
    revenue: float
    playtime_minutes: float
    pre_playtime_minutes: float
    crashed: int
    session_count: int


def _binary(value: str, field: str) -> int:
    parsed = int(value)
    if parsed not in (0, 1):
        raise ValueError(f"{field} must be 0 or 1")
    return parsed


def load_metrics(path: str | Path) -> tuple[UserMetric, ...]:
    source = Path(path)
    with source.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = REQUIRED_COLUMNS - set(reader.fieldnames or ())
        if missing:
            raise ValueError(f"missing columns: {', '.join(sorted(missing))}")
        rows = []
        seen_users = set()
        for line_number, row in enumerate(reader, start=2):
            user_id = row["user_id"].strip()
            if not user_id:
                raise ValueError(f"line {line_number}: empty user_id")
            if user_id in seen_users:
                raise ValueError(f"line {line_number}: duplicate user_id {user_id}")
            seen_users.add(user_id)
            variant = row["variant"].strip().upper()
            if variant not in ("A", "B"):
                raise ValueError(f"line {line_number}: variant must be A or B")
            metric = UserMetric(
                user_id=user_id,
                variant=variant,
                d7_retained=_binary(row["d7_retained"], "d7_retained"),
                payer=_binary(row["payer"], "payer"),
                revenue=float(row["revenue"]),
                playtime_minutes=float(row["playtime_minutes"]),
                pre_playtime_minutes=float(row["pre_playtime_minutes"]),
                crashed=_binary(row["crashed"], "crashed"),
                session_count=int(row["session_count"]),
            )
            if min(
                metric.revenue,
                metric.playtime_minutes,
                metric.pre_playtime_minutes,
                metric.session_count,
            ) < 0:
                raise ValueError(f"line {line_number}: metrics cannot be negative")
            rows.append(metric)
    if len(rows) < 100:
        raise ValueError("at least 100 user rows are required")
    return tuple(rows)


def _proportion_metric(
    name: str,
    control: tuple[UserMetric, ...],
    treatment: tuple[UserMetric, ...],
    attribute: str,
    *,
    note: str = "",
) -> MetricResult:
    effect = difference_in_proportions(
        sum(int(getattr(row, attribute)) for row in control),
        len(control),
        sum(int(getattr(row, attribute)) for row in treatment),
        len(treatment),
    )
    return MetricResult(
        name=name,
        kind="proportion",
        control=effect.control,
        treatment=effect.treatment,
        absolute=effect.absolute,
        relative=effect.relative,
        p_value=effect.p_value,
        ci_low=effect.ci_low,
        ci_high=effect.ci_high,
        note=note,
    )


def _mean_metric(
    name: str,
    control_values: tuple[float, ...],
    treatment_values: tuple[float, ...],
    *,
    note: str = "",
) -> MetricResult:
    effect = difference_in_means(control_values, treatment_values)
    return MetricResult(
        name=name,
        kind="mean",
        control=effect.control,
        treatment=effect.treatment,
        absolute=effect.absolute,
        relative=effect.relative,
        p_value=effect.p_value,
        ci_low=effect.ci_low,
        ci_high=effect.ci_high,
        note=note,
    )


class ExperimentAnalyzer:
    def __init__(
        self,
        *,
        experiment_name: str = "game_version_ab",
        minimum_detectable_effect: float = 0.015,
        alpha: float = 0.05,
        srm_alpha: float = 0.001,
    ):
        self.experiment_name = experiment_name
        self.minimum_detectable_effect = minimum_detectable_effect
        self.alpha = alpha
        self.srm_alpha = srm_alpha

    def analyze(self, csv_path: str | Path) -> ExperimentResult:
        rows = load_metrics(csv_path)
        control = tuple(row for row in rows if row.variant == "A")
        treatment = tuple(row for row in rows if row.variant == "B")
        if min(len(control), len(treatment)) < 30:
            raise ValueError("each variant needs at least 30 users")

        srm_chi_square, srm_p_value = srm_test(len(control), len(treatment))
        srm_passed = srm_p_value >= self.srm_alpha

        primary = _proportion_metric(
            "D7 留存率",
            control,
            treatment,
            "d7_retained",
            note="双侧合并方差 z 检验；95% CI 使用非合并标准误。",
        )
        revenue = _mean_metric(
            "每用户收入（ARPU）",
            tuple(row.revenue for row in control),
            tuple(row.revenue for row in treatment),
            note="Welch 标准误的大样本正态近似。",
        )
        sessions = _mean_metric(
            "人均会话数",
            tuple(float(row.session_count) for row in control),
            tuple(float(row.session_count) for row in treatment),
        )
        payer = _proportion_metric(
            "付费率", control, treatment, "payer", note="业务诊断指标。"
        )

        cuped = cuped_adjust(
            tuple(row.playtime_minutes for row in control),
            tuple(row.pre_playtime_minutes for row in control),
            tuple(row.playtime_minutes for row in treatment),
            tuple(row.pre_playtime_minutes for row in treatment),
        )
        cuped_metric = MetricResult(
            name="CUPED 调整后人均游戏时长（分钟）",
            kind="mean",
            control=cuped.control_mean,
            treatment=cuped.treatment_mean,
            absolute=cuped.absolute,
            relative=(
                cuped.absolute / cuped.control_mean
                if abs(cuped.control_mean) > 1e-12
                else None
            ),
            p_value=cuped.p_value,
            ci_low=cuped.ci_low,
            ci_high=cuped.ci_high,
            note=f"协变量为实验前游戏时长；方差降低 {cuped.variance_reduction:.1%}。",
        )

        crash_effect = difference_in_proportions(
            sum(row.crashed for row in control),
            len(control),
            sum(row.crashed for row in treatment),
            len(treatment),
        )
        crash_margin = 0.005
        crash_guardrail = GuardrailResult(
            name="崩溃用户率",
            control=crash_effect.control,
            treatment=crash_effect.treatment,
            absolute=crash_effect.absolute,
            margin=crash_margin,
            passed=crash_effect.ci_high < crash_margin,
            p_value=crash_effect.p_value,
            rule=f"95% CI 上界 < +{crash_margin:.2%}",
        )
        payer_effect = difference_in_proportions(
            sum(row.payer for row in control),
            len(control),
            sum(row.payer for row in treatment),
            len(treatment),
        )
        payer_margin = -0.003
        payer_guardrail = GuardrailResult(
            name="付费率非劣",
            control=payer_effect.control,
            treatment=payer_effect.treatment,
            absolute=payer_effect.absolute,
            margin=payer_margin,
            passed=payer_effect.ci_low > payer_margin,
            p_value=payer_effect.p_value,
            rule=f"95% CI 下界 > {payer_margin:.2%}",
        )
        guardrails = (crash_guardrail, payer_guardrail)

        safe_baseline = min(0.98, max(0.02, primary.control))
        planned_users_per_group = required_sample_size_for_proportion(
            safe_baseline, self.minimum_detectable_effect, alpha=self.alpha
        )
        information_fraction = min(
            1.0,
            (len(control) + len(treatment)) / (2.0 * planned_users_per_group),
        )
        _, sequential_p_threshold = obrien_fleming_threshold(
            max(information_fraction, 1e-6), alpha=self.alpha
        )

        reasons = []
        if not srm_passed:
            decision = "实验无效：先排查分流"
            reasons.append(
                f"SRM p={srm_p_value:.4g}，低于阈值 {self.srm_alpha:g}。"
            )
        elif not all(guardrail.passed for guardrail in guardrails):
            decision = "暂不推广：护栏未通过"
            failed_names = "、".join(
                guardrail.name for guardrail in guardrails if not guardrail.passed
            )
            reasons.append(f"未通过护栏：{failed_names}。")
        elif (
            primary.absolute > 0.0
            and primary.p_value < sequential_p_threshold
            and primary.ci_low > 0.0
        ):
            decision = "建议推广 B 版本"
            reasons.append(
                "D7 留存提升为正，且通过当前信息比例下的序贯显著性边界。"
            )
            reasons.append("崩溃率与付费率护栏均通过。")
        else:
            decision = "继续实验并补足样本"
            reasons.append(
                "主指标尚未同时满足正向效应、置信区间和序贯显著性要求。"
            )

        return ExperimentResult(
            experiment_name=self.experiment_name,
            control_users=len(control),
            treatment_users=len(treatment),
            srm_chi_square=srm_chi_square,
            srm_p_value=srm_p_value,
            srm_passed=srm_passed,
            primary=primary,
            secondary=(revenue, sessions, payer),
            guardrails=guardrails,
            cuped_theta=cuped.theta,
            cuped_variance_reduction=cuped.variance_reduction,
            cuped_metric=cuped_metric,
            planned_users_per_group=planned_users_per_group,
            information_fraction=information_fraction,
            sequential_p_threshold=sequential_p_threshold,
            decision=decision,
            reasons=tuple(reasons),
        )
