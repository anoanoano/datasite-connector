#!/usr/bin/env python3
"""
Official MCP Server implementation for HTTP transport
"""
import asyncio
import logging
import json
from typing import Any, Dict, Optional

from mcp.server import Server
import mcp.types as types
from mcp.server.session import ServerSession

# For HTTP transport, we'll use FastAPI with proper MCP integration
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn

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
        logger.info("Initializing DataSite components for official MCP server...")
        
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

# Create official MCP server
mcp_server = Server("datasite-connector")

@mcp_server.list_tools()
async def list_tools() -> list[types.Tool]:
    """List available MCP tools using official SDK."""
    logger.info("Official MCP list_tools called")
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

@mcp_server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    """Handle tool calls using official SDK."""
    try:
        logger.info(f"Official MCP tool called: {name} with arguments: {arguments}")
        
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
        
        return [types.TextContent(
            type="text",
            text=json.dumps(result, indent=2)
        )]
        
    except Exception as e:
        logger.error(f"Error in official MCP tool call {name}: {e}")
        error_result = {"success": False, "error": str(e)}
        return [types.TextContent(
            type="text",
            text=json.dumps(error_result, indent=2)
        )]

# Create FastAPI app for HTTP transport
app = FastAPI(
    title="DataSite MCP Server",
    description="Official MCP server for DataSite content access",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Handle MCP requests through HTTP
@app.post("/")
async def handle_mcp_request(request: Request):
    """Handle MCP requests via HTTP POST."""
    try:
        data = await request.json()
        logger.info(f"Official MCP HTTP request: {data}")
        
        # Create a simple transport mock for the official server
        class HTTPTransport:
            def __init__(self):
                self.request_queue = asyncio.Queue()
                self.response_queue = asyncio.Queue()
            
            async def send_message(self, message):
                await self.response_queue.put(message)
            
            async def receive_message(self):
                return data
        
        transport = HTTPTransport()
        
        # Create server session with the transport
        session = ServerSession(mcp_server, transport.receive_message, transport.send_message)
        
        # Process the message
        await session.handle_message(data)
        
        # Get the response
        response = await asyncio.wait_for(transport.response_queue.get(), timeout=5.0)
        return JSONResponse(content=response)
        
    except Exception as e:
        logger.error(f"Error in official MCP HTTP handler: {e}")
        return JSONResponse(
            content={
                "jsonrpc": "2.0",
                "id": data.get("id") if 'data' in locals() else None,
                "error": {
                    "code": -32603,
                    "message": "Internal error",
                    "data": str(e)
                }
            },
            status_code=500
        )

@app.get("/")
async def root():
    """Root endpoint for discovery."""
    return {
        "name": "DataSite MCP Server",
        "version": "1.0.0",
        "protocol": "MCP",
        "transport": "http"
    }

@app.on_event("startup")
async def startup_event():
    """Initialize components on startup."""
    await initialize_components()

if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8082,
        log_level="info"
    )