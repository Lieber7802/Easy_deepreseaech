import asyncio
from typing import Any, Optional, Dict
from pydantic import BaseModel, Field
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from src.core.skills.base import Skill, SkillRegistry

class MCPClientSkill(Skill):
    """A Skill that wraps a tool from an external MCP Server."""
    
    def __init__(self, mcp_tool_name: str, mcp_tool_description: str, mcp_input_schema: Dict[str, Any], server_command: str, server_args: list[str]):
        self.name = mcp_tool_name
        self.description = mcp_tool_description
        self.version = "1.0.0"
        self.mcp_tool_name = mcp_tool_name
        
        # We store server params to connect on demand
        self.server_params = StdioServerParameters(
            command=server_command,
            args=server_args,
            env=None 
        )
        
        # Note: Mapping MCP JSON schema to Pydantic model dynamically is complex.
        # For simplicity in this demo, we accept arbitrary kwargs and rely on MCP client validation.
        self.input_schema = None 

    def execute(self, **kwargs) -> Any:
        """Execute the MCP tool via stdio connection."""
        return asyncio.run(self._execute_async(**kwargs))

    async def _execute_async(self, **kwargs) -> Any:
        async with stdio_client(self.server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                
                # List tools to verify existence (optional but good for debugging)
                # tools = await session.list_tools()
                
                # Call the tool
                result = await session.call_tool(self.mcp_tool_name, arguments=kwargs)
                
                # Format result
                if result.isError:
                    return f"MCP Tool Error: {result.content}"
                
                # Extract text content
                texts = [c.text for c in result.content if c.type == 'text']
                return "\n".join(texts)

# Helper to load tools from a local MCP server (e.g. filesystem server)
async def load_local_mcp_tools(command: str, args: list[str]):
    """Connect to a local MCP server and register its tools as Skills."""
    try:
        server_params = StdioServerParameters(command=command, args=args)
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools_response = await session.list_tools()
                
                for tool_info in tools_response.tools:
                    # Create a skill wrapper for each tool
                    skill = MCPClientSkill(
                        mcp_tool_name=tool_info.name,
                        mcp_tool_description=tool_info.description or "No description",
                        mcp_input_schema=tool_info.inputSchema,
                        server_command=command,
                        server_args=args
                    )
                    SkillRegistry.register(skill)
                    print(f"Loaded MCP Tool: {tool_info.name}")
                    
    except Exception as e:
        print(f"Failed to load MCP tools from {command}: {e}")
