from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from .analysis import ExperimentAnalyzer
from .report import write_html_report
from .simulator import simulate_experiment


def _write_json(payload: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _analyze(input_path: Path, output_dir: Path, experiment_name: str) -> dict:
    started = time.perf_counter()
    analyzer = ExperimentAnalyzer(experiment_name=experiment_name)
    result = analyzer.analyze(input_path)
    elapsed = time.perf_counter() - started
    report_path = write_html_report(result, output_dir / "report.html")
    payload = result.to_dict()
    payload["runtime_seconds"] = elapsed
    payload["input_path"] = str(input_path)
    payload["report_path"] = str(report_path)
    _write_json(payload, output_dir / "analysis.json")
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="experiment-guard",
        description="游戏版本 A/B 实验评估：SRM、功效、CUPED、护栏与序贯边界。",
    )
    subparsers = parser.add_subparsers(dest="command")

    demo = subparsers.add_parser("demo", help="生成可复现样例并输出 HTML 报告")
    demo.add_argument("--output-dir", type=Path, default=Path("demo_output"))
    demo.add_argument("--users", type=int, default=20_000)
    demo.add_argument("--seed", type=int, default=20260726)
    demo.add_argument("--experiment-name", default="new_player_path_v2")

    simulate = subparsers.add_parser("simulate", help="只生成用户级 CSV")
    simulate.add_argument("output", type=Path)
    simulate.add_argument("--users", type=int, default=20_000)
    simulate.add_argument("--seed", type=int, default=20260726)
    simulate.add_argument("--retention-uplift", type=float, default=0.018)

    analyze = subparsers.add_parser("analyze", help="分析已有用户级 CSV")
    analyze.add_argument("input", type=Path)
    analyze.add_argument("--output-dir", type=Path, default=Path("analysis_output"))
    analyze.add_argument("--experiment-name", default="game_version_ab")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    command = args.command or "demo"

    if command == "simulate":
        path = simulate_experiment(
            args.output,
            users=args.users,
            seed=args.seed,
            retention_uplift=args.retention_uplift,
        )
        print(json.dumps({"csv": str(path), "users": args.users}, ensure_ascii=False))
        return 0

    if command == "analyze":
        payload = _analyze(args.input, args.output_dir, args.experiment_name)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    output_dir = getattr(args, "output_dir", Path("demo_output"))
    users = getattr(args, "users", 20_000)
    seed = getattr(args, "seed", 20260726)
    experiment_name = getattr(args, "experiment_name", "new_player_path_v2")
    output_dir.mkdir(parents=True, exist_ok=True)
    simulate_started = time.perf_counter()
    csv_path = simulate_experiment(
        output_dir / "experiment_users.csv", users=users, seed=seed
    )
    simulate_elapsed = time.perf_counter() - simulate_started
    payload = _analyze(csv_path, output_dir, experiment_name)
    payload["simulation_seconds"] = simulate_elapsed
    payload["total_runtime_seconds"] = (
        simulate_elapsed + float(payload["runtime_seconds"])
    )
    _write_json(payload, output_dir / "analysis.json")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

