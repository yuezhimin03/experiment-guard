from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Iterable, Sequence


EPSILON = 1e-12


@dataclass(frozen=True)
class Effect:
    control: float
    treatment: float
    absolute: float
    relative: float | None
    standard_error: float
    statistic: float
    p_value: float
    ci_low: float
    ci_high: float


@dataclass(frozen=True)
class CupedResult:
    theta: float
    control_mean: float
    treatment_mean: float
    absolute: float
    p_value: float
    ci_low: float
    ci_high: float
    variance_reduction: float
    adjusted_control: tuple[float, ...]
    adjusted_treatment: tuple[float, ...]


def normal_cdf(value: float) -> float:
    return 0.5 * (1.0 + math.erf(value / math.sqrt(2.0)))


def normal_quantile(probability: float) -> float:
    """Inverse standard-normal CDF using Peter J. Acklam's approximation."""
    if not 0.0 < probability < 1.0:
        raise ValueError("probability must be strictly between 0 and 1")

    a = (
        -3.969683028665376e01,
        2.209460984245205e02,
        -2.759285104469687e02,
        1.383577518672690e02,
        -3.066479806614716e01,
        2.506628277459239e00,
    )
    b = (
        -5.447609879822406e01,
        1.615858368580409e02,
        -1.556989798598866e02,
        6.680131188771972e01,
        -1.328068155288572e01,
    )
    c = (
        -7.784894002430293e-03,
        -3.223964580411365e-01,
        -2.400758277161838e00,
        -2.549732539343734e00,
        4.374664141464968e00,
        2.938163982698783e00,
    )
    d = (
        7.784695709041462e-03,
        3.224671290700398e-01,
        2.445134137142996e00,
        3.754408661907416e00,
    )
    low = 0.02425
    high = 1.0 - low
    if probability < low:
        q = math.sqrt(-2.0 * math.log(probability))
        return (
            (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5])
            / ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1.0)
        )
    if probability <= high:
        q = probability - 0.5
        r = q * q
        return (
            (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5])
            * q
            / (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1.0)
        )
    q = math.sqrt(-2.0 * math.log(1.0 - probability))
    return -(
        (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5])
        / ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1.0)
    )


def mean(values: Sequence[float]) -> float:
    if not values:
        raise ValueError("at least one value is required")
    return math.fsum(values) / len(values)


def sample_variance(values: Sequence[float]) -> float:
    if len(values) < 2:
        raise ValueError("at least two values are required")
    center = mean(values)
    return math.fsum((value - center) ** 2 for value in values) / (len(values) - 1)


def covariance(left: Sequence[float], right: Sequence[float]) -> float:
    if len(left) != len(right) or len(left) < 2:
        raise ValueError("paired samples of equal length are required")
    left_mean = mean(left)
    right_mean = mean(right)
    return math.fsum(
        (x - left_mean) * (y - right_mean) for x, y in zip(left, right)
    ) / (len(left) - 1)


def two_sided_p_value(statistic: float) -> float:
    return max(0.0, min(1.0, 2.0 * (1.0 - normal_cdf(abs(statistic)))))


def difference_in_proportions(
    control_successes: int,
    control_total: int,
    treatment_successes: int,
    treatment_total: int,
    alpha: float = 0.05,
) -> Effect:
    if min(control_total, treatment_total) <= 0:
        raise ValueError("group sizes must be positive")
    if not 0 <= control_successes <= control_total:
        raise ValueError("invalid control successes")
    if not 0 <= treatment_successes <= treatment_total:
        raise ValueError("invalid treatment successes")

    control_rate = control_successes / control_total
    treatment_rate = treatment_successes / treatment_total
    absolute = treatment_rate - control_rate
    relative = absolute / control_rate if control_rate > EPSILON else None
    pooled = (control_successes + treatment_successes) / (
        control_total + treatment_total
    )
    pooled_se = math.sqrt(
        max(
            pooled
            * (1.0 - pooled)
            * (1.0 / control_total + 1.0 / treatment_total),
            EPSILON,
        )
    )
    statistic = absolute / pooled_se
    ci_se = math.sqrt(
        max(
            control_rate * (1.0 - control_rate) / control_total
            + treatment_rate * (1.0 - treatment_rate) / treatment_total,
            EPSILON,
        )
    )
    critical = normal_quantile(1.0 - alpha / 2.0)
    return Effect(
        control=control_rate,
        treatment=treatment_rate,
        absolute=absolute,
        relative=relative,
        standard_error=pooled_se,
        statistic=statistic,
        p_value=two_sided_p_value(statistic),
        ci_low=absolute - critical * ci_se,
        ci_high=absolute + critical * ci_se,
    )


def difference_in_means(
    control: Sequence[float],
    treatment: Sequence[float],
    alpha: float = 0.05,
) -> Effect:
    if len(control) < 2 or len(treatment) < 2:
        raise ValueError("each group must have at least two observations")
    control_mean = mean(control)
    treatment_mean = mean(treatment)
    absolute = treatment_mean - control_mean
    relative = absolute / control_mean if abs(control_mean) > EPSILON else None
    standard_error = math.sqrt(
        sample_variance(control) / len(control)
        + sample_variance(treatment) / len(treatment)
    )
    standard_error = max(standard_error, EPSILON)
    statistic = absolute / standard_error
    critical = normal_quantile(1.0 - alpha / 2.0)
    return Effect(
        control=control_mean,
        treatment=treatment_mean,
        absolute=absolute,
        relative=relative,
        standard_error=standard_error,
        statistic=statistic,
        p_value=two_sided_p_value(statistic),
        ci_low=absolute - critical * standard_error,
        ci_high=absolute + critical * standard_error,
    )


def srm_test(
    control_total: int,
    treatment_total: int,
    expected_control_share: float = 0.5,
) -> tuple[float, float]:
    if control_total + treatment_total <= 0:
        raise ValueError("at least one observation is required")
    if not 0.0 < expected_control_share < 1.0:
        raise ValueError("expected share must be between 0 and 1")
    total = control_total + treatment_total
    expected_control = total * expected_control_share
    expected_treatment = total - expected_control
    chi_square = (
        (control_total - expected_control) ** 2 / expected_control
        + (treatment_total - expected_treatment) ** 2 / expected_treatment
    )
    # For one degree of freedom, the survival function is erfc(sqrt(x / 2)).
    p_value = math.erfc(math.sqrt(chi_square / 2.0))
    return chi_square, p_value


def cuped_adjust(
    control_outcome: Sequence[float],
    control_covariate: Sequence[float],
    treatment_outcome: Sequence[float],
    treatment_covariate: Sequence[float],
    alpha: float = 0.05,
) -> CupedResult:
    if len(control_outcome) != len(control_covariate):
        raise ValueError("control outcome and covariate lengths differ")
    if len(treatment_outcome) != len(treatment_covariate):
        raise ValueError("treatment outcome and covariate lengths differ")
    outcomes = tuple(control_outcome) + tuple(treatment_outcome)
    covariates = tuple(control_covariate) + tuple(treatment_covariate)
    covariate_variance = sample_variance(covariates)
    theta = (
        covariance(outcomes, covariates) / covariate_variance
        if covariate_variance > EPSILON
        else 0.0
    )
    covariate_center = mean(covariates)
    adjusted_control = tuple(
        outcome - theta * (covariate - covariate_center)
        for outcome, covariate in zip(control_outcome, control_covariate)
    )
    adjusted_treatment = tuple(
        outcome - theta * (covariate - covariate_center)
        for outcome, covariate in zip(treatment_outcome, treatment_covariate)
    )
    adjusted_effect = difference_in_means(
        adjusted_control, adjusted_treatment, alpha=alpha
    )
    raw_variance = sample_variance(outcomes)
    adjusted_variance = sample_variance(adjusted_control + adjusted_treatment)
    variance_reduction = (
        max(0.0, min(1.0, 1.0 - adjusted_variance / raw_variance))
        if raw_variance > EPSILON
        else 0.0
    )
    return CupedResult(
        theta=theta,
        control_mean=mean(adjusted_control),
        treatment_mean=mean(adjusted_treatment),
        absolute=adjusted_effect.absolute,
        p_value=adjusted_effect.p_value,
        ci_low=adjusted_effect.ci_low,
        ci_high=adjusted_effect.ci_high,
        variance_reduction=variance_reduction,
        adjusted_control=adjusted_control,
        adjusted_treatment=adjusted_treatment,
    )


def bootstrap_difference_in_means(
    control: Sequence[float],
    treatment: Sequence[float],
    *,
    samples: int = 1000,
    alpha: float = 0.05,
    seed: int = 20260726,
) -> tuple[float, float]:
    if len(control) < 2 or len(treatment) < 2:
        raise ValueError("each group must have at least two observations")
    if samples < 100:
        raise ValueError("use at least 100 bootstrap samples")
    rng = random.Random(seed)
    differences = []
    for _ in range(samples):
        control_mean = math.fsum(
            control[rng.randrange(len(control))] for _ in range(len(control))
        ) / len(control)
        treatment_mean = math.fsum(
            treatment[rng.randrange(len(treatment))] for _ in range(len(treatment))
        ) / len(treatment)
        differences.append(treatment_mean - control_mean)
    differences.sort()
    low_index = max(0, int((alpha / 2.0) * samples))
    high_index = min(samples - 1, int((1.0 - alpha / 2.0) * samples) - 1)
    return differences[low_index], differences[high_index]


def required_sample_size_for_proportion(
    baseline: float,
    minimum_detectable_effect: float,
    *,
    alpha: float = 0.05,
    power: float = 0.8,
) -> int:
    treatment = baseline + minimum_detectable_effect
    if not 0.0 < baseline < 1.0 or not 0.0 < treatment < 1.0:
        raise ValueError("baseline and treatment rate must lie between 0 and 1")
    if not 0.0 < power < 1.0:
        raise ValueError("power must lie between 0 and 1")
    pooled = (baseline + treatment) / 2.0
    z_alpha = normal_quantile(1.0 - alpha / 2.0)
    z_power = normal_quantile(power)
    numerator = (
        z_alpha * math.sqrt(2.0 * pooled * (1.0 - pooled))
        + z_power
        * math.sqrt(
            baseline * (1.0 - baseline) + treatment * (1.0 - treatment)
        )
    ) ** 2
    return math.ceil(numerator / (minimum_detectable_effect**2))


def obrien_fleming_threshold(
    information_fraction: float, alpha: float = 0.05
) -> tuple[float, float]:
    if not 0.0 < information_fraction <= 1.0:
        raise ValueError("information fraction must be in (0, 1]")
    critical = normal_quantile(1.0 - alpha / 2.0) / math.sqrt(
        information_fraction
    )
    p_threshold = two_sided_p_value(critical)
    return critical, p_threshold


def as_float_tuple(values: Iterable[float]) -> tuple[float, ...]:
    return tuple(float(value) for value in values)
