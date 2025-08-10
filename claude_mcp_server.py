#!/usr/bin/env python3
"""
Claude-compatible MCP Server for DataSite Content Access
Implements MCP Streamable HTTP transport as expected by Claude browser
"""
import asyncio
import json
import logging
from typing import Any, Dict, Optional

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
import uvicorn

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
        logger.info("Initializing DataSite components for Claude MCP server...")
        
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

# Create FastAPI app
app = FastAPI(
    title="DataSite MCP Server",
    description="Claude-compatible MCP server for DataSite content access",
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

# Create MCP server
mcp_server = Server("datasite-connector")

@mcp_server.list_tools()
async def list_tools() -> list[types.Tool]:
    """List available MCP tools."""
    logger.info("Claude MCP list_tools called")
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
    """Handle tool calls from Claude."""
    try:
        logger.info(f"Claude MCP tool called: {name} with arguments: {arguments}")
        
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
        logger.error(f"Error in Claude MCP tool call {name}: {e}")
        error_result = {"success": False, "error": str(e)}
        return [types.TextContent(
            type="text",
            text=json.dumps(error_result, indent=2)
        )]

# MCP Streamable HTTP Transport Implementation

@app.get("/")
async def root():
    """Root endpoint for MCP discovery."""
    logger.info("GET / called for MCP discovery")
    return {
        "name": "DataSite MCP Server",
        "version": "1.0.0",
        "protocol": "MCP Streamable HTTP",
        "transport": "streamable-http"
    }

@app.post("/")
async def handle_mcp_root(request: Request):
    """Handle MCP requests at root."""
    logger.info(f"POST / called from {request.client}")
    return await handle_mcp_message(request)

@app.get("/mcp")
async def mcp_discovery():
    """MCP endpoint discovery."""
    logger.info("GET /mcp called for MCP discovery")
    return {
        "name": "DataSite MCP Server",
        "version": "1.0.0",
        "protocol": "MCP Streamable HTTP", 
        "transport": "streamable-http"
    }

@app.post("/mcp")
async def handle_mcp_endpoint(request: Request):
    """Handle MCP requests at /mcp endpoint."""
    logger.info(f"POST /mcp called from {request.client}")
    return await handle_mcp_message(request)

@app.head("/mcp")
async def handle_mcp_head():
    """Handle MCP HEAD requests."""
    logger.info("HEAD /mcp called")
    return Response(headers={
        "mcp-protocol-version": "2024-11-05",
        "content-type": "application/json"
    })

async def handle_mcp_message(request: Request):
    """Handle MCP JSON-RPC messages."""
    try:
        data = await request.json()
        logger.info(f"Received MCP message: {json.dumps(data, indent=2)}")
        
        method = data.get("method")
        params = data.get("params", {})
        request_id = data.get("id")
        
        if method == "initialize":
            # Claude's initialization request
            logger.info(f"Initialize request with params: {params}")
            # Use the client's preferred protocol version if we support it
            client_version = params.get("protocolVersion", "2024-11-05")
            supported_versions = ["2024-11-05", "2025-06-18"]
            protocol_version = client_version if client_version in supported_versions else "2024-11-05"
            
            response = {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "protocolVersion": protocol_version,
                    "capabilities": {
                        "tools": {
                            "listChanged": True
                        }
                    },
                    "serverInfo": {
                        "name": "datasite-connector",
                        "version": "1.0.0"
                    }
                }
            }
            logger.info(f"Initialize response: {json.dumps(response, indent=2)}")
        
        elif method == "notifications/initialized":
            # Handle initialized notification
            logger.info("Received notifications/initialized")
            return Response(status_code=204)  # No content for notifications
        
        elif method == "tools/list":
            # List available tools
            logger.info("Received tools/list request")
            tools = await list_tools()
            tools_data = []
            for tool in tools:
                tools_data.append({
                    "name": tool.name,
                    "description": tool.description,
                    "inputSchema": tool.inputSchema
                })
            
            response = {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "tools": tools_data
                }
            }
            logger.info(f"tools/list response: {json.dumps(response, indent=2)}")
        
        elif method == "tools/call":
            # Handle tool calls
            tool_name = params.get("name")
            arguments = params.get("arguments", {})
            logger.info(f"tools/call: {tool_name} with args {arguments}")
            
            result = await call_tool(tool_name, arguments)
            content_data = []
            for item in result:
                content_data.append({
                    "type": item.type,
                    "text": item.text
                })
            
            response = {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "content": content_data
                }
            }
            logger.info(f"tools/call response: {json.dumps(response, indent=2)}")
        
        else:
            # Unknown method
            logger.warning(f"Unknown method: {method}")
            response = {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32601,
                    "message": f"Method not found: {method}"
                }
            }
        
        return JSONResponse(content=response)
        
    except Exception as e:
        logger.error(f"Error handling MCP message: {e}")
        error_response = {
            "jsonrpc": "2.0",
            "id": data.get("id") if 'data' in locals() else None,
            "error": {
                "code": -32603,
                "message": "Internal error",
                "data": str(e)
            }
        }
        return JSONResponse(content=error_response, status_code=500)

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