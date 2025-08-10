#!/usr/bin/env python3
"""
Standalone MCP Server for Claude integration.
This creates a proper MCP server that Claude can connect to.
"""

import asyncio
import json
import logging
from pathlib import Path
from mcp.server import Server, NotificationOptions
from mcp.server.models import InitializationOptions
import mcp.server.stdio
import mcp.types as types

from src.config import Config
from src.content_repository import ContentRepository
from src.datasite_manager import DataSiteManager
from src.access_control import AccessControlSystem

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global components
config = None
content_repo = None
datasite_manager = None
access_control = None

async def initialize_components():
    """Initialize all DataSite components."""
    global config, content_repo, datasite_manager, access_control
    
    config = Config()
    
    # Initialize components
    datasite_manager = DataSiteManager(config)
    await datasite_manager.initialize()
    
    content_repo = ContentRepository(config)
    await content_repo.initialize()
    
    access_control = AccessControlSystem(config)
    await access_control.initialize()
    
    logger.info("DataSite components initialized successfully")

# Create MCP server
server = Server("datasite-connector")

@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
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
                        "description": "Filter datasets by tags"
                    },
                    "content_type": {
                        "type": "string",
                        "description": "Filter by content type"
                    }
                }
            }
        ),
        types.Tool(
            name="get_content",
            description="Retrieve specific content from the datasite",
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
                "required": ["dataset_name"]
            }
        ),
        types.Tool(
            name="search_content",
            description="Search content based on query",
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
                        "description": "Maximum number of results",
                        "default": 10
                    }
                },
                "required": ["query"]
            }
        ),
        types.Tool(
            name="get_content_summary",
            description="Get privacy-preserving summary of content",
            inputSchema={
                "type": "object",
                "properties": {
                    "dataset_name": {
                        "type": "string",
                        "description": "Name of the dataset"
                    },
                    "summary_type": {
                        "type": "string",
                        "enum": ["statistical", "semantic", "structural"],
                        "description": "Type of summary to generate",
                        "default": "semantic"
                    }
                },
                "required": ["dataset_name"]
            }
        )
    ]

@server.call_tool()
async def handle_call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    """Handle tool calls from Claude."""
    try:
        logger.info(f"Tool called: {name} with args: {arguments}")
        
        if name == "list_datasets":
            tags_filter = arguments.get("tags", [])
            content_type_filter = arguments.get("content_type")
            
            datasets = await content_repo.list_datasets(
                tags_filter=tags_filter,
                content_type_filter=content_type_filter
            )
            
            dataset_list = []
            for name, metadata in datasets.items():
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
                        "data": {
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
                summary = await content_repo.get_content_summary(
                    dataset_name, summary_type="semantic"
                )
                result = {"success": True, "summary": summary}
                
            else:  # raw format
                content = await content_repo.get_content(dataset_name)
                if content:
                    try:
                        content_str = content.decode('utf-8')
                        result = {
                            "success": True,
                            "content": content_str,
                            "size": len(content)
                        }
                    except UnicodeDecodeError:
                        result = {
                            "success": True,
                            "content": f"[Binary content: {len(content)} bytes]",
                            "size": len(content),
                            "note": "Content is binary and cannot be displayed as text"
                        }
                else:
                    result = {"success": False, "error": "Content not found"}
        
        elif name == "search_content":
            query = arguments["query"]
            max_results = arguments.get("max_results", 10)
            
            results = await content_repo.search_content(
                query=query,
                max_results=max_results
            )
            
            result = {
                "success": True,
                "results": results,
                "query": query,
                "result_count": len(results)
            }
            
        elif name == "get_content_summary":
            dataset_name = arguments["dataset_name"]
            summary_type = arguments.get("summary_type", "semantic")
            
            summary = await content_repo.get_content_summary(
                dataset_name, summary_type
            )
            
            if summary:
                result = {
                    "success": True,
                    "summary": summary,
                    "type": summary_type
                }
            else:
                result = {"success": False, "error": "Could not generate summary"}
                
        else:
            result = {"success": False, "error": f"Unknown tool: {name}"}
        
        return [types.TextContent(
            type="text", 
            text=json.dumps(result, indent=2)
        )]
        
    except Exception as e:
        logger.error(f"Tool call error: {e}")
        error_result = {"success": False, "error": f"Internal error: {str(e)}"}
        return [types.TextContent(
            type="text", 
            text=json.dumps(error_result, indent=2)
        )]

async def main():
    """Main server function."""
    # Initialize components first
    await initialize_components()
    
    # Run the MCP server
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="datasite-connector",
                server_version="1.0.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                )
            )
        )

if __name__ == "__main__":
    asyncio.run(main())