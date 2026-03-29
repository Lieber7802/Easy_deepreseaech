from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field

class TodoItem(BaseModel):
    id: int
    title: str
    intent: str
    query: str
    status: str = "pending"  # pending, in_progress, completed, failed, skipped
    summary: Optional[str] = None
    sources_summary: Optional[str] = None
    note_id: Optional[str] = None
    note_path: Optional[str] = None
    stream_token: Optional[str] = None
    notices: List[str] = []

class ResearchRequest(BaseModel):
    topic: str
    search_api: Optional[str] = None
    run_id: Optional[str] = None
    experiment_id: Optional[str] = None
    dataset_id: Optional[str] = None
    sample_id: Optional[str] = None
    eval_mode: Optional[str] = None
    evaluation_enabled: Optional[bool] = None
    agentic_rag_mode: Optional[str] = Field(
        default=None,
        description="classic | agentic | both"
    )

class ResearchResponse(BaseModel):
    report_markdown: str
    todo_items: List[Dict[str, Any]]
