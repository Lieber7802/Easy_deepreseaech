"""Graph state definitions and data structures for the Deep Research agent."""

import operator
from typing import Annotated, Optional

from langchain_core.messages import MessageLikeRepresentation
from langgraph.graph import MessagesState
from pydantic import BaseModel, Field
from typing_extensions import TypedDict


###################
# Structured Outputs
###################
class ConductResearch(BaseModel):
    """Call this tool to conduct research on a specific topic."""
    research_topic: str = Field(
        description="The topic to research. Should be a single topic, and should be described in high detail (at least a paragraph).",
    )

class ResearchComplete(BaseModel):
    """Call this tool to indicate that the research is complete."""

class Summary(BaseModel):
    """Research summary with key findings."""
    
    summary: str
    key_excerpts: str

class ClarifyWithUser(BaseModel):
    """Result of analyzing whether user input needs clarification."""
    
    need_clarification: bool = Field(
        description="Whether the user needs to be asked a clarifying question.",
    )
    question: str = Field(
        description="A clarifying question to ask the user if need_clarification is True. If False, provide an empty string.",
    )
    verification: str = Field(
        description="A confirmation message to tell the user research is starting if need_clarification is False. If True, provide an empty string.",
    )

class ResearchQuestion(BaseModel):
    """Research question and brief for guiding research."""
    
    research_brief: str = Field(
        description="A research question that will be used to guide the research.",
    )

class QueryAnalysisResult(BaseModel):
    """Result of query analysis for Agentic RAG routing."""
    
    route: str = Field(
        description="Routing decision: local_kb, web_search, or direct_answer.",
    )
    needs_rewrite: bool = Field(
        description="Whether the query should be rewritten for better retrieval.",
    )
    needs_decomposition: bool = Field(
        description="Whether the query should be decomposed into sub-queries.",
    )
    rationale: str = Field(
        description="Brief reason for the routing and optimization decisions.",
    )

class QueryRewriteResult(BaseModel):
    """Rewritten query for improved retrieval."""
    
    rewritten_query: str = Field(
        description="A rewritten query that improves retrieval quality while preserving intent.",
    )

class QueryDecompositionResult(BaseModel):
    """Decomposed sub-queries for complex question retrieval."""
    
    sub_queries: list[str] = Field(
        description="2-3 focused sub-queries that cover the original question.",
    )

class DocumentGradeResult(BaseModel):
    """Relevance grading result for a retrieved document chunk."""
    
    relevant: bool = Field(
        description="Whether the retrieved document is relevant to the query.",
    )
    reason: str = Field(
        description="Short reason for the relevance judgment.",
    )

class HallucinationCheckResult(BaseModel):
    """Groundedness check result for generated answer."""
    
    grounded: bool = Field(
        description="Whether every major claim in the draft is grounded in provided evidence.",
    )
    reason: str = Field(
        description="Short explanation of the groundedness decision.",
    )


###################
# State Definitions
###################

def override_reducer(current_value, new_value):
    """Reducer function that allows overriding values in state."""
    if isinstance(new_value, dict) and new_value.get("type") == "override":
        return new_value.get("value", new_value)
    else:
        return operator.add(current_value, new_value)
    
class AgentInputState(MessagesState):
    """InputState is only 'messages'."""

class AgentState(MessagesState):
    """Main agent state containing messages and research data."""
    
    supervisor_messages: Annotated[list[MessageLikeRepresentation], override_reducer]
    research_brief: Optional[str]
    raw_notes: Annotated[list[str], override_reducer] = []
    notes: Annotated[list[str], override_reducer] = []
    final_report: str

class SupervisorState(TypedDict):
    """State for the supervisor that manages research tasks."""
    
    supervisor_messages: Annotated[list[MessageLikeRepresentation], override_reducer]
    research_brief: str
    notes: Annotated[list[str], override_reducer] = []
    research_iterations: int = 0
    raw_notes: Annotated[list[str], override_reducer] = []

class ResearcherState(TypedDict):
    """State for individual researchers conducting research."""
    
    researcher_messages: Annotated[list[MessageLikeRepresentation], operator.add]
    tool_call_iterations: int = 0
    research_topic: str
    compressed_research: str
    raw_notes: Annotated[list[str], override_reducer] = []

class ResearcherOutputState(BaseModel):
    """Output state from individual researchers."""
    
    compressed_research: str
    raw_notes: Annotated[list[str], override_reducer] = []

class AgenticRAGState(TypedDict):
    """State for Agentic RAG subgraph execution."""
    
    query: str
    rewritten_query: str
    sub_queries: list[str]
    retrieval_queries: list[str]
    retrieved_docs: Annotated[list[dict], operator.add]
    graded_docs: Annotated[list[dict], operator.add]
    retry_count: int
    max_retries: int
    knowledge_gap: bool
    draft_answer: str
    final_answer: str
    route: str
    trace: Annotated[list[str], operator.add]
