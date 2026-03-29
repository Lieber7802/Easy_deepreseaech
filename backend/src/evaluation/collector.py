from __future__ import annotations

import json
import os
import threading
from typing import Any, Dict, Optional

from langchain_core.runnables import RunnableConfig

from src.evaluation.schema import EvaluationContext, EvaluationEvent


class EvaluationCollector:
    def __init__(self, output_file: str):
        self.output_file = output_file
        os.makedirs(os.path.dirname(self.output_file), exist_ok=True)
        self._lock = threading.Lock()

    def emit(self, event: EvaluationEvent) -> None:
        line = json.dumps(event.model_dump(), ensure_ascii=False)
        with self._lock:
            with open(self.output_file, "a", encoding="utf-8") as f:
                f.write(line + "\n")

    def emit_from_context(
        self,
        context: EvaluationContext,
        event_type: str,
        payload: Optional[Dict[str, Any]] = None,
        component: Optional[str] = None,
    ) -> None:
        event = EvaluationEvent(
            event_type=event_type,
            run_id=context.run_id,
            experiment_id=context.experiment_id,
            dataset_id=context.dataset_id,
            sample_id=context.sample_id,
            eval_mode=context.eval_mode,
            rag_mode=context.rag_mode,
            component=component,
            payload=payload or {},
        )
        self.emit(event)


def get_collector(output_file: Optional[str] = None) -> EvaluationCollector:
    path = output_file or os.getenv(
        "EVALUATION_EVENTS_FILE",
        os.path.join("data", "evaluations", "evaluation_events.jsonl"),
    )
    return EvaluationCollector(path)


def context_from_runnable_config(config: RunnableConfig | None) -> Optional[EvaluationContext]:
    configurable = (config or {}).get("configurable", {})
    if not configurable.get("evaluation_enabled", False):
        return None
    run_id = configurable.get("run_id")
    if not run_id:
        return None
    return EvaluationContext(
        run_id=str(run_id),
        experiment_id=configurable.get("experiment_id"),
        dataset_id=configurable.get("dataset_id"),
        sample_id=configurable.get("sample_id"),
        eval_mode=str(configurable.get("eval_mode", "online")),
        rag_mode=configurable.get("agentic_rag_mode"),
    )


def emit_metric_from_runnable_config(
    config: RunnableConfig | None,
    event_type: str,
    payload: Optional[Dict[str, Any]] = None,
    component: Optional[str] = None,
) -> None:
    context = context_from_runnable_config(config)
    if context is None:
        return
    collector = get_collector()
    collector.emit_from_context(
        context=context,
        event_type=event_type,
        payload=payload or {},
        component=component,
    )
