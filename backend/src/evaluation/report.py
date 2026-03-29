from __future__ import annotations

import json
from collections import defaultdict
from typing import Any, Dict

from src.evaluation.schema import EvaluationReport, ModeSummary


def _safe_avg(total: float, count: int) -> float:
    if count <= 0:
        return 0.0
    return total / count


def generate_report_from_events_file(
    events_file: str,
    experiment_id: str | None = None,
    dataset_id: str | None = None,
) -> EvaluationReport:
    mode_totals: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))
    mode_counts: Dict[str, int] = defaultdict(int)
    mode_completed: Dict[str, int] = defaultdict(int)
    mode_failed: Dict[str, int] = defaultdict(int)

    with open(events_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except Exception:
                continue

            if experiment_id and event.get("experiment_id") != experiment_id:
                continue
            if dataset_id and event.get("dataset_id") != dataset_id:
                continue

            mode = str(event.get("rag_mode") or "both")
            event_type = event.get("event_type")
            payload: Dict[str, Any] = event.get("payload") or {}

            if event_type == "run_started":
                mode_counts[mode] += 1
            elif event_type == "run_finished":
                status = payload.get("status")
                if status == "completed":
                    mode_completed[mode] += 1
                elif status == "failed":
                    mode_failed[mode] += 1
                mode_totals[mode]["total_latency_ms"] += float(payload.get("total_latency_ms", 0))
                mode_totals[mode]["first_event_latency_ms"] += float(payload.get("first_event_latency_ms", 0))
                mode_totals[mode]["tasks_created"] += float(payload.get("tasks_created", 0))
                mode_totals[mode]["tool_calls"] += float(payload.get("tool_calls", 0))
            elif event_type == "agentic_rag_summary":
                mode_totals[mode]["fallback_rate"] += float(payload.get("fallback_rate", 0))
                mode_totals[mode]["grader_pass_rate"] += float(payload.get("grader_pass_rate", 0))
                mode_totals[mode]["grounded_pass_rate"] += float(payload.get("grounded_pass_rate", 0))
                mode_totals[mode]["agentic_count"] += 1

    summaries: Dict[str, ModeSummary] = {}
    for mode in ("classic", "agentic", "both"):
        run_count = mode_counts.get(mode, 0)
        totals = mode_totals.get(mode, {})
        agentic_count = int(totals.get("agentic_count", 0))
        summaries[mode] = ModeSummary(
            mode=mode,  # type: ignore[arg-type]
            total_runs=run_count,
            completed_runs=mode_completed.get(mode, 0),
            failed_runs=mode_failed.get(mode, 0),
            avg_total_latency_ms=_safe_avg(totals.get("total_latency_ms", 0.0), run_count),
            avg_first_event_latency_ms=_safe_avg(totals.get("first_event_latency_ms", 0.0), run_count),
            avg_tasks_created=_safe_avg(totals.get("tasks_created", 0.0), run_count),
            avg_tool_calls=_safe_avg(totals.get("tool_calls", 0.0), run_count),
            avg_fallback_rate=_safe_avg(totals.get("fallback_rate", 0.0), agentic_count),
            avg_grader_pass_rate=_safe_avg(totals.get("grader_pass_rate", 0.0), agentic_count),
            avg_grounded_pass_rate=_safe_avg(totals.get("grounded_pass_rate", 0.0), agentic_count),
        )

    deltas: Dict[str, Dict[str, float]] = {}
    if summaries["classic"].total_runs and summaries["agentic"].total_runs:
        deltas["agentic_vs_classic"] = {
            "latency_ms_delta": summaries["agentic"].avg_total_latency_ms - summaries["classic"].avg_total_latency_ms,
            "fallback_rate_delta": summaries["agentic"].avg_fallback_rate - summaries["classic"].avg_fallback_rate,
            "grader_pass_rate_delta": summaries["agentic"].avg_grader_pass_rate - summaries["classic"].avg_grader_pass_rate,
            "grounded_pass_rate_delta": summaries["agentic"].avg_grounded_pass_rate - summaries["classic"].avg_grounded_pass_rate,
        }

    return EvaluationReport(
        experiment_id=experiment_id,
        dataset_id=dataset_id,
        summaries=summaries,
        deltas=deltas,
    )
