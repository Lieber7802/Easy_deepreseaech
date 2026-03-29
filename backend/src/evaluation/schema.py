from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel, Field


def utc_iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class EvaluationContext(BaseModel):
    run_id: str
    experiment_id: Optional[str] = None
    dataset_id: Optional[str] = None
    sample_id: Optional[str] = None
    eval_mode: str = "online"
    rag_mode: Optional[str] = None


class EvaluationEvent(BaseModel):
    event_type: str
    timestamp: str = Field(default_factory=utc_iso_now)
    run_id: str
    experiment_id: Optional[str] = None
    dataset_id: Optional[str] = None
    sample_id: Optional[str] = None
    eval_mode: str = "online"
    rag_mode: Optional[str] = None
    component: Optional[str] = None
    payload: Dict[str, Any] = Field(default_factory=dict)


class ModeSummary(BaseModel):
    mode: Literal["classic", "agentic", "both"]
    total_runs: int = 0
    completed_runs: int = 0
    failed_runs: int = 0
    avg_total_latency_ms: float = 0.0
    avg_first_event_latency_ms: float = 0.0
    avg_tasks_created: float = 0.0
    avg_tool_calls: float = 0.0
    avg_fallback_rate: float = 0.0
    avg_grader_pass_rate: float = 0.0
    avg_grounded_pass_rate: float = 0.0


class EvaluationReport(BaseModel):
    generated_at: str = Field(default_factory=utc_iso_now)
    experiment_id: Optional[str] = None
    dataset_id: Optional[str] = None
    summaries: Dict[str, ModeSummary] = Field(default_factory=dict)
    deltas: Dict[str, Dict[str, float]] = Field(default_factory=dict)
