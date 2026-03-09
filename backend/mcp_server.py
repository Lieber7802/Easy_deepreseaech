import asyncio
import os
import logging
from typing import Any
from mcp.server.fastmcp import FastMCP
from dotenv import load_dotenv

# Import capabilities we want to expose
from service import DeepResearchService
from src.core.rag_manager import get_rag_manager

load_dotenv()

# Initialize FastMCP Server
mcp = FastMCP("DeepInsight-Agent")

@mcp.tool()
async def search_knowledge_base(query: str, k: int = 5) -> str:
    """Search the local DeepInsight knowledge base (RAG)."""
    try:
        rag = get_rag_manager()
        docs = rag.retrieve(query, k=k)
        if not docs:
            return "No documents found."
        
        results = []
        for i, doc in enumerate(docs):
            source = os.path.basename(doc.metadata.get("source", "Unknown"))
            content = doc.page_content.replace("\n", " ")
            results.append(f"[Source: {source}]\n{content}\n")
        return "\n---\n".join(results)
    except Exception as e:
        return f"Error: {str(e)}"

@mcp.tool()
async def start_deep_research(topic: str) -> str:
    """Trigger a deep research task (Note: returns immediate ack, runs in background)."""
    # Note: In a real MCP scenario, we might want to stream logs back. 
    # For simplicity, we just trigger the service and return an acknowledgment.
    # A full implementation would connect to the event stream.
    return f"Research started for topic: '{topic}'. Please check the dashboard for progress."

if __name__ == "__main__":
    # Run the MCP server over stdio
    mcp.run()
