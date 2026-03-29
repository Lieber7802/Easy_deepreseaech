import asyncio
from typing import Any, List, Optional
from pydantic import Field, BaseModel

from src.core.skills.base import Skill, SkillRegistry
from langchain_core.tools import tool
import arxiv

# 1. Migrate Builtin Skills

class TavilySearchSkill(Skill):
    name: str = "tavily_search"
    description: str = "Web search engine optimized for comprehensive results."
    version: str = "1.0.0"
    
    def execute(self, **kwargs) -> Any:
        from src.core.utils import tavily_search
        return tavily_search.invoke(kwargs)

class RAGSearchSkill(Skill):
    name: str = "search_knowledge_base"
    description: str = "Search local knowledge base (uploaded documents)."
    version: str = "1.0.0"
    
    def execute(self, **kwargs) -> Any:
        from src.core.utils import search_knowledge_base
        return search_knowledge_base.invoke(kwargs)

class AgenticRAGSearchSkill(Skill):
    name: str = "agentic_knowledge_base"
    description: str = "Agentic RAG search for local knowledge with grading, rewrite, and fallback."
    version: str = "1.0.0"
    
    def execute(self, **kwargs) -> Any:
        from src.core.utils import agentic_knowledge_base
        return agentic_knowledge_base.invoke(kwargs)

# 2. Add New Skill: Arxiv Search

class ArxivSearchInput(BaseModel):
    query: str = Field(description="Search query for Arxiv")
    max_results: int = Field(default=5, description="Max number of papers to return")

class ArxivSearchSkill(Skill):
    name: str = "arxiv_search"
    description: str = "Search for academic papers on Arxiv."
    version: str = "0.1.0"
    input_schema: Optional[type[BaseModel]] = ArxivSearchInput

    def execute(self, query: str, max_results: int = 5) -> str:
        try:
            client = arxiv.Client()
            search = arxiv.Search(
                query=query,
                max_results=max_results,
                sort_by=arxiv.SortCriterion.Relevance
            )
            
            results = []
            for result in client.results(search):
                results.append(
                    f"Title: {result.title}\n"
                    f"Authors: {', '.join(a.name for a in result.authors)}\n"
                    f"Published: {result.published.date()}\n"
                    f"Summary: {result.summary.replace('\n', ' ')}\n"
                    f"URL: {result.entry_id}\n"
                )
            
            if not results:
                return "No papers found."
                
            return "\n---\n".join(results)
        except Exception as e:
            return f"Error searching Arxiv: {str(e)}"

# Register Skills
def register_builtin_skills():
    SkillRegistry.register(TavilySearchSkill())
    SkillRegistry.register(RAGSearchSkill())
    SkillRegistry.register(AgenticRAGSearchSkill())
    SkillRegistry.register(ArxivSearchSkill())
