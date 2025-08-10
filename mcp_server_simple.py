#!/usr/bin/env python3
"""
Simple MCP Server for Claude Desktop integration.
"""

import asyncio
import json
import logging
import sys

from mcp.server import Server
import mcp.server.stdio
import mcp.types as types

from src.config import Config
from src.content_repository import ContentRepository
from src.datasite_manager import DataSiteManager
from src.access_control import AccessControlSystem

# Configure logging to stderr so it doesn't interfere with MCP protocol
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger(__name__)

# Global components
app_components = {}

async def initialize_components():
    """Initialize all DataSite components."""
    try:
        logger.info("Initializing DataSite components...")
        
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

# Create MCP server
server = Server("datasite-connector")

@server.list_tools()
async def list_tools() -> list[types.Tool]:
    """List available MCP tools."""
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
                    },
                    "format": {
                        "type": "string",
                        "enum": ["raw", "summary", "metadata"],
                        "description": "Format of the returned content",
                        "default": "raw"
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
                    },
                    "max_results": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 50,
                        "description": "Maximum number of results to return",
                        "default": 10
                    }
                },
                "required": ["query"],
                "additionalProperties": False
            }
        )
    ]

@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    """Handle tool calls from Claude."""
    try:
        logger.info(f"Tool called: {name} with arguments: {arguments}")
        
        content_repo = app_components.get('content_repo')
        if not content_repo:
            raise Exception("Content repository not initialized")
        
        if name == "list_datasets":
            # Get optional tags filter
            tags_filter = arguments.get("tags", [])
            
            # List datasets
            datasets = await content_repo.list_datasets(tags_filter=tags_filter)
            
            # Format response
            dataset_list = []
            for dataset_name, metadata in datasets.items():
                dataset_info = {
                    "name": metadata.name,
                    "description": metadata.description,
                    "content_type": metadata.content_type,
                    "size": metadata.size,
                    "tags": metadata.tags,
                    "created_at": metadata.created_at
                }
                dataset_list.append(dataset_info)
            
            result = {
                "success": True,
                "datasets": dataset_list,
                "total_count": len(dataset_list)
            }
        
        elif name == "get_content":
            dataset_name = arguments["dataset_name"]
            format_type = arguments.get("format", "raw")
            
            if format_type == "metadata":
                metadata = await content_repo.get_metadata(dataset_name)
                if metadata:
                    result = {
                        "success": True,
                        "metadata": {
                            "name": metadata.name,
                            "description": metadata.description,
                            "content_type": metadata.content_type,
                            "size": metadata.size,
                            "tags": metadata.tags,
                            "created_at": metadata.created_at
                        }
                    }
                else:
                    result = {"success": False, "error": "Dataset not found"}
            
            elif format_type == "summary":
                summary = await content_repo.get_content_summary(dataset_name, "semantic")
                result = {
                    "success": True,
                    "summary": summary if summary else "Could not generate summary"
                }
            
            else:  # raw format
                content = await content_repo.get_content(dataset_name)
                if content:
                    try:
                        content_str = content.decode('utf-8')
                        result = {
                            "success": True,
                            "content": content_str,
                            "size": len(content),
                            "dataset_name": dataset_name
                        }
                    except UnicodeDecodeError:
                        result = {
                            "success": False,
                            "error": "Content contains non-UTF-8 data and cannot be displayed as text"
                        }
                else:
                    result = {"success": False, "error": "Dataset not found"}
        
        elif name == "search_content":
            query = arguments["query"]
            max_results = arguments.get("max_results", 10)
            
            results = await content_repo.search_content(query=query, max_results=max_results)
            
            result = {
                "success": True,
                "query": query,
                "results": results,
                "result_count": len(results)
            }
        
        else:
            result = {"success": False, "error": f"Unknown tool: {name}"}
        
        # Return as TextContent
        return [types.TextContent(
            type="text",
            text=json.dumps(result, indent=2)
        )]
        
    except Exception as e:
        logger.error(f"Error in tool call {name}: {e}")
        error_result = {"success": False, "error": str(e)}
        return [types.TextContent(
            type="text",
            text=json.dumps(error_result, indent=2)
        )]

async def main():
    """Main server function."""
    # Initialize components
    await initialize_components()
    
    # Run MCP server over stdio
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )

if __name__ == "__main__":
    asyncio.run(main())