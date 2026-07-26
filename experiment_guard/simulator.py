from __future__ import annotations

import csv
import math
import random
from pathlib import Path


FIELDNAMES = (
    "user_id",
    "variant",
    "d7_retained",
    "payer",
    "revenue",
    "playtime_minutes",
    "pre_playtime_minutes",
    "crashed",
    "session_count",
)


def _clamp_probability(value: float) -> float:
    return max(0.001, min(0.999, value))


def simulate_experiment(
    output_path: str | Path,
    *,
    users: int = 20_000,
    seed: int = 20260726,
    retention_uplift: float = 0.018,
    treatment_share: float = 0.5,
) -> Path:
    """Write deterministic user-level game experiment data to CSV."""
    if users < 200:
        raise ValueError("users must be at least 200")
    if not 0.05 <= treatment_share <= 0.95:
        raise ValueError("treatment_share must be between 0.05 and 0.95")

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader()
        for user_number in range(1, users + 1):
            variant = "B" if rng.random() < treatment_share else "A"
            is_treatment = variant == "B"

            pre_playtime = rng.gammavariate(2.2, 18.0)
            engagement_signal = min(0.16, pre_playtime / 360.0)
            retained_probability = _clamp_probability(
                0.19
                + engagement_signal
                + (retention_uplift if is_treatment else 0.0)
            )
            retained = int(rng.random() < retained_probability)

            playtime = max(
                0.0,
                12.0
                + 0.72 * pre_playtime
                + 12.0 * retained
                + (3.0 if is_treatment else 0.0)
                + rng.gauss(0.0, 17.0),
            )
            payer_probability = _clamp_probability(
                0.035 + 0.045 * retained + min(pre_playtime / 5000.0, 0.02)
            )
            payer = int(rng.random() < payer_probability)
            revenue = (
                min(399.0, rng.lognormvariate(math.log(18.0), 0.85))
                if payer
                else 0.0
            )
            crash_probability = 0.0215 + (0.0010 if is_treatment else 0.0)
            crashed = int(rng.random() < crash_probability)
            session_count = max(
                1,
                int(
                    round(
                        1.0
                        + pre_playtime / 28.0
                        + retained * 2.2
                        + rng.gauss(0.0, 1.0)
                    )
                ),
            )
            writer.writerow(
                {
                    "user_id": f"u{user_number:07d}",
                    "variant": variant,
                    "d7_retained": retained,
                    "payer": payer,
                    "revenue": f"{revenue:.4f}",
                    "playtime_minutes": f"{playtime:.4f}",
                    "pre_playtime_minutes": f"{pre_playtime:.4f}",
                    "crashed": crashed,
                    "session_count": session_count,
                }
            )
    return path

