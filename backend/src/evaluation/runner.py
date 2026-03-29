from __future__ import annotations

import argparse
import asyncio
import json
import os
import uuid
from typing import Any, Dict, List

from service import DeepResearchService
from src.evaluation.report import generate_report_from_events_file


def load_dataset(dataset_path: str) -> List[Dict[str, Any]]:
    samples: List[Dict[str, Any]] = []
    with open(dataset_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            samples.append(json.loads(line))
    return samples


async def run_single_sample(
    service: DeepResearchService,
    sample: Dict[str, Any],
    rag_mode: str,
    experiment_id: str,
    dataset_id: str,
) -> None:
    topic = str(sample.get("topic", "")).strip()
    sample_id = str(sample.get("sample_id") or uuid.uuid4())
    if not topic:
        return
    run_id = str(uuid.uuid4())

    async for _ in service.run_stream(
        topic=topic,
        search_api=str(sample.get("search_api", "tavily")),
        run_id=run_id,
        experiment_id=experiment_id,
        dataset_id=dataset_id,
        sample_id=sample_id,
        eval_mode="offline_benchmark",
        agentic_rag_mode=rag_mode,
        evaluation_enabled=True,
    ):
        pass


async def run_dataset(
    dataset_path: str,
    rag_mode: str,
    experiment_id: str,
    dataset_id: str,
) -> None:
    service = DeepResearchService()
    samples = load_dataset(dataset_path)
    for sample in samples:
        await run_single_sample(
            service=service,
            sample=sample,
            rag_mode=rag_mode,
            experiment_id=experiment_id,
            dataset_id=dataset_id,
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run offline evaluation benchmark")
    parser.add_argument("--dataset", required=True, help="Path to dataset jsonl")
    parser.add_argument("--mode", choices=["classic", "agentic", "both"], default="both")
    parser.add_argument("--experiment-id", default=f"exp-{uuid.uuid4().hex[:8]}")
    parser.add_argument("--dataset-id", default=None)
    parser.add_argument("--events-file", default=None)
    args = parser.parse_args()

    dataset_id = args.dataset_id or os.path.splitext(os.path.basename(args.dataset))[0]
    if args.events_file:
        os.environ["EVALUATION_EVENTS_FILE"] = args.events_file

    asyncio.run(
        run_dataset(
            dataset_path=args.dataset,
            rag_mode=args.mode,
            experiment_id=args.experiment_id,
            dataset_id=dataset_id,
        )
    )

    events_file = os.getenv("EVALUATION_EVENTS_FILE", os.path.join("data", "evaluations", "evaluation_events.jsonl"))
    report = generate_report_from_events_file(
        events_file=events_file,
        experiment_id=args.experiment_id,
        dataset_id=dataset_id,
    )
    print(json.dumps(report.model_dump(), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
