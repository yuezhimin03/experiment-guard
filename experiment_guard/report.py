from __future__ import annotations

import html
from pathlib import Path

from .models import ExperimentResult, GuardrailResult, MetricResult


def _percent(value: float) -> str:
    return f"{value:.2%}"


def _number(value: float) -> str:
    return f"{value:,.3f}"


def _metric_value(metric: MetricResult, value: float) -> str:
    return _percent(value) if metric.kind == "proportion" else _number(value)


def _metric_row(metric: MetricResult) -> str:
    relative = "—" if metric.relative is None else _percent(metric.relative)
    return f"""
      <tr>
        <td><strong>{html.escape(metric.name)}</strong><small>{html.escape(metric.note)}</small></td>
        <td>{_metric_value(metric, metric.control)}</td>
        <td>{_metric_value(metric, metric.treatment)}</td>
        <td class="{'positive' if metric.absolute > 0 else 'negative'}">{_metric_value(metric, metric.absolute)}</td>
        <td>{relative}</td>
        <td>{metric.p_value:.4g}</td>
        <td>[{_metric_value(metric, metric.ci_low)}, {_metric_value(metric, metric.ci_high)}]</td>
      </tr>
    """


def _guardrail_row(guardrail: GuardrailResult) -> str:
    return f"""
      <tr>
        <td><strong>{html.escape(guardrail.name)}</strong><small>{html.escape(guardrail.rule)}</small></td>
        <td>{_percent(guardrail.control)}</td>
        <td>{_percent(guardrail.treatment)}</td>
        <td>{_percent(guardrail.absolute)}</td>
        <td>{guardrail.p_value:.4g}</td>
        <td><span class="status {'pass' if guardrail.passed else 'fail'}">{'通过' if guardrail.passed else '未通过'}</span></td>
      </tr>
    """


def write_html_report(
    result: ExperimentResult, output_path: str | Path
) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    metrics = (result.primary,) + result.secondary + (result.cuped_metric,)
    reasons = "".join(f"<li>{html.escape(reason)}</li>" for reason in result.reasons)
    metric_rows = "".join(_metric_row(metric) for metric in metrics)
    guardrail_rows = "".join(_guardrail_row(item) for item in result.guardrails)
    decision_class = (
        "pass"
        if result.decision.startswith("建议")
        else "fail"
        if "无效" in result.decision or "暂不" in result.decision
        else "wait"
    )
    document = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(result.experiment_name)} - ExperimentGuard</title>
  <style>
    :root {{
      color-scheme: light;
      --ink: #172033;
      --muted: #64748b;
      --line: #dbe3ee;
      --surface: #ffffff;
      --canvas: #f4f7fb;
      --blue: #2457d6;
      --green: #13795b;
      --red: #b42318;
      --amber: #a15c00;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0; background: var(--canvas); color: var(--ink);
      font: 15px/1.55 Inter, "Microsoft YaHei", system-ui, sans-serif;
    }}
    main {{ width: min(1180px, calc(100% - 32px)); margin: 32px auto 64px; }}
    header {{
      background: linear-gradient(135deg, #102a68, #2457d6);
      color: white; border-radius: 18px; padding: 30px 34px;
      box-shadow: 0 16px 40px rgba(23, 49, 104, .16);
    }}
    header p {{ margin: 4px 0 0; color: #dce7ff; }}
    h1 {{ margin: 0; font-size: 29px; }}
    h2 {{ font-size: 19px; margin: 0 0 14px; }}
    .decision {{
      display: inline-block; margin-top: 18px; padding: 8px 14px;
      border-radius: 999px; font-weight: 700; background: white; color: var(--blue);
    }}
    .grid {{
      display: grid; grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 14px; margin: 18px 0;
    }}
    .card, section {{
      background: var(--surface); border: 1px solid var(--line);
      border-radius: 14px; box-shadow: 0 6px 20px rgba(32, 52, 85, .06);
    }}
    .card {{ padding: 18px; }}
    .card span {{ display: block; color: var(--muted); font-size: 13px; }}
    .card strong {{ display: block; margin-top: 4px; font-size: 22px; }}
    section {{ margin-top: 18px; padding: 22px; overflow-x: auto; }}
    table {{ width: 100%; border-collapse: collapse; min-width: 850px; }}
    th, td {{ padding: 11px 10px; border-bottom: 1px solid var(--line); text-align: right; }}
    th:first-child, td:first-child {{ text-align: left; }}
    th {{ color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: .04em; }}
    td small {{ display: block; margin-top: 2px; color: var(--muted); font-weight: 400; }}
    .positive {{ color: var(--green); }}
    .negative {{ color: var(--red); }}
    .status {{ display: inline-block; border-radius: 99px; padding: 3px 9px; font-weight: 700; }}
    .pass {{ color: var(--green); background: #e7f6f0; }}
    .fail {{ color: var(--red); background: #fff0ee; }}
    .wait {{ color: var(--amber); background: #fff5df; }}
    ul {{ margin: 0; padding-left: 20px; }}
    footer {{ margin-top: 18px; color: var(--muted); text-align: center; font-size: 12px; }}
    @media (max-width: 760px) {{ .grid {{ grid-template-columns: repeat(2, 1fr); }} }}
  </style>
</head>
<body>
<main>
  <header>
    <h1>ExperimentGuard · 游戏版本实验评估</h1>
    <p>{html.escape(result.experiment_name)} · 可复现统计口径与护栏决策</p>
    <span class="decision {decision_class}">{html.escape(result.decision)}</span>
  </header>

  <div class="grid">
    <div class="card"><span>A 组用户</span><strong>{result.control_users:,}</strong></div>
    <div class="card"><span>B 组用户</span><strong>{result.treatment_users:,}</strong></div>
    <div class="card"><span>SRM p-value</span><strong>{result.srm_p_value:.4g}</strong></div>
    <div class="card"><span>当前信息比例</span><strong>{result.information_fraction:.1%}</strong></div>
  </div>

  <section>
    <h2>结论依据</h2>
    <ul>{reasons}</ul>
  </section>

  <section>
    <h2>主指标与诊断指标</h2>
    <table>
      <thead><tr><th>指标</th><th>A 组</th><th>B 组</th><th>绝对差</th><th>相对差</th><th>p-value</th><th>95% CI</th></tr></thead>
      <tbody>{metric_rows}</tbody>
    </table>
  </section>

  <section>
    <h2>护栏指标</h2>
    <table>
      <thead><tr><th>护栏</th><th>A 组</th><th>B 组</th><th>绝对差</th><th>p-value</th><th>判定</th></tr></thead>
      <tbody>{guardrail_rows}</tbody>
    </table>
  </section>

  <section>
    <h2>实验完整性与功效</h2>
    <ul>
      <li>SRM χ² = {result.srm_chi_square:.4f}，分流检查：{'通过' if result.srm_passed else '未通过'}。</li>
      <li>按当前 A 组留存和 MDE 规划，每组目标样本 {result.planned_users_per_group:,}。</li>
      <li>O'Brien-Fleming 当前双侧 p-value 边界：{result.sequential_p_threshold:.4g}。</li>
      <li>CUPED θ = {result.cuped_theta:.4f}，游戏时长方差降低 {result.cuped_variance_reduction:.1%}。</li>
    </ul>
  </section>
  <footer>本报告由 ExperimentGuard 生成。正态近似适用于大样本；业务上线仍需结合分层、长期效应与数据质量复核。</footer>
</main>
</body>
</html>
"""
    path.write_text(document, encoding="utf-8")
    return path

