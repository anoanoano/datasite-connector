#!/usr/bin/env python3
"""
Proper MCP Server using official Python SDK
"""
import asyncio
import logging
from mcp.server.fastmcp import FastMCP
from mcp.server import Server
import mcp.types as types

from src.config import Config
from src.content_repository import ContentRepository
from src.datasite_manager import DataSiteManager
from src.access_control import AccessControlSystem

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global components
app_components = {}

async def initialize_components():
    """Initialize all DataSite components."""
    try:
        logger.info("Initializing DataSite components for proper MCP server...")
        
        config = Config()
        
        # Initialize components
        datasite_manager = DataSiteManager(config)
        await datasite_manager.initialize()
        
        content_repo = ContentRepository(config)
        await content_repo.initialize()
        
        access_control = AccessControlSystem(config)
        await access_control.initialize()
        
        app_components.update({
            'config': config,
            'datasite_manager': datasite_manager,
            'content_repo': content_repo,
            'access_control': access_control
        })
        
        logger.info("DataSite components initialized successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize components: {e}")
        raise

# Create proper MCP server using official SDK
server = Server("datasite-connector")

@server.list_tools()
async def list_tools() -> list[types.Tool]:
    """List available MCP tools using official SDK."""
    return [
        types.Tool(
            name="list_datasets",
            description="List all available datasets in the datasite",
            inputSchema={
                "type": "object",
                "properties": {
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional: Filter datasets by tags"
                    }
                },
                "additionalProperties": False
            }
        ),
        types.Tool(
            name="get_content",
            description="Retrieve content from a specific dataset",
            inputSchema={
                "type": "object",
                "properties": {
                    "dataset_name": {
                        "type": "string",
                        "description": "Name of the dataset to retrieve"
                    }
                },
                "required": ["dataset_name"],
                "additionalProperties": False
            }
        ),
        types.Tool(
            name="search_content",
            description="Search for content across all datasets",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query"
                    }
                },
                "required": ["query"],
                "additionalProperties": False
            }
        )
    ]

@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    """Handle tool calls using official SDK."""
    try:
        logger.info(f"Proper MCP tool called: {name} with arguments: {arguments}")
        
        content_repo = app_components.get('content_repo')
        if not content_repo:
            raise Exception("Content repository not initialized")
        
        if name == "list_datasets":
            datasets = await content_repo.list_datasets()
            dataset_list = []
            for dataset_name, metadata in datasets.items():
                dataset_list.append({
                    "name": metadata.name,
                    "description": metadata.description,
                    "content_type": metadata.content_type,
                    "size": metadata.size,
                    "tags": metadata.tags
                })
            
            result = {"success": True, "datasets": dataset_list}
        
        elif name == "get_content":
            dataset_name = arguments["dataset_name"]
            content = await content_repo.get_content(dataset_name)
            if content:
                result = {
                    "success": True,
                    "content": content.decode('utf-8', errors='ignore'),
                    "dataset_name": dataset_name
                }
            else:
                result = {"success": False, "error": "Dataset not found"}
        
        elif name == "search_content":
            query = arguments["query"]
            results = await content_repo.search_content(query=query)
            result = {"success": True, "results": results}
        
        else:
            result = {"success": False, "error": f"Unknown tool: {name}"}
        
        import json
        return [types.TextContent(
            type="text",
            text=json.dumps(result, indent=2)
        )]
        
    except Exception as e:
        logger.error(f"Error in proper MCP tool call {name}: {e}")
        import json
        error_result = {"success": False, "error": str(e)}
        return [types.TextContent(
            type="text",
            text=json.dumps(error_result, indent=2)
        )]

async def main():
    """Main server function."""
    # Initialize components
    await initialize_components()
    
    # Run MCP server using official SDK
    from mcp.server.sse import SseServerTransport
    from mcp.server.stdio import stdio_server
    
    logger.info("Starting proper MCP server...")
    
    # Use stdio transport for proper MCP
    async with stdio_server() as streams:
        await server.run(*streams)

if __name__ == "__main__":
    asyncio.run(main())