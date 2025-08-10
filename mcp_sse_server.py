#!/usr/bin/env python3
"""
HTTP+SSE MCP Server for Claude Remote MCP Connector
Implements the legacy HTTP with Server-Sent Events transport (2024-11-05 spec)
"""

import asyncio
import json
import logging
from typing import Any, Dict, Optional
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from sse_starlette import EventSourceResponse
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
        logger.info("Initializing DataSite components for MCP SSE server...")
        
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
    description="MCP-compatible server for DataSite content access (HTTP+SSE)",
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
        logger.info(f"MCP SSE tool called: {name}")
        
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
        logger.error(f"Error in MCP SSE tool: {e}")
        return [types.TextContent(
            type="text",
            text=json.dumps({"success": False, "error": str(e)})
        )]

# Store active sessions
active_sessions = {}

@app.post("/mcp/")
async def handle_mcp_streamable(request: Request):
    """Handle MCP Streamable HTTP requests."""
    return await handle_message(request)

@app.get("/mcp/")
async def handle_mcp_get():
    """Handle MCP GET requests for discovery."""
    return {
        "protocol": "MCP",
        "version": "1.0.0",
        "transport": {
            "type": "http",
            "endpoint": "/mcp/"
        },
        "capabilities": {
            "tools": ["list_datasets", "get_content", "search_content"]
        }
    }

# Add missing /mcp endpoints that Claude expects
@app.post("/mcp")
async def handle_mcp_post(request: Request):
    """Handle MCP POST requests."""
    logger.info(f"POST /mcp called from {request.client}")
    return await handle_mcp_request(request)

@app.get("/mcp")
async def handle_mcp_get_no_slash():
    """Handle MCP GET requests for discovery."""
    return {
        "protocol": "MCP",
        "version": "1.0.0",
        "transport": {
            "type": "http",
            "endpoint": "/mcp"
        },
        "capabilities": {
            "tools": ["list_datasets", "get_content", "search_content"]
        }
    }

@app.head("/mcp")
async def handle_mcp_head():
    """Handle MCP HEAD requests."""
    from starlette.responses import Response
    return Response(headers={
        "mcp-protocol-version": "2025-06-18",
        "content-type": "application/json"
    })

# Remove OAuth discovery endpoints - let them 404 to signal no OAuth support

@app.post("/messages")  
async def handle_message(request: Request):
    """Handle MCP JSON-RPC messages over HTTP POST."""
    logger.info(f"POST /messages called from {request.client}")
    return await handle_mcp_request(request)

async def handle_mcp_request(request: Request):
    """Common MCP request handler."""
    try:
        data = await request.json()
        logger.info(f"Received MCP message: {data}")
        
        method = data.get("method")
        params = data.get("params", {})
        request_id = data.get("id")
        
        if method == "initialize":
            # Use the client's protocol version if supported
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
                        },
                        "logging": {},
                        "prompts": {
                            "listChanged": True
                        },
                        "resources": {
                            "subscribe": True,
                            "listChanged": True
                        }
                    },
                    "serverInfo": {
                        "name": "datasite-connector",
                        "title": "DataSite MCP Server", 
                        "version": "1.0.0"
                    }
                }
            }
        
        elif method == "tools/list":
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
        
        elif method == "tools/call":
            tool_name = params.get("name")
            arguments = params.get("arguments", {})
            
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
        
        elif method == "notifications/initialized":
            # Handle initialized notification - return empty response for notifications
            from starlette.responses import Response
            return Response(status_code=204)
        
        else:
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

@app.get("/events")
async def events_stream(request: Request):
    """Handle Server-Sent Events stream for MCP notifications."""
    
    async def event_publisher():
        """Generate server-sent events."""
        try:
            # Send initial connection confirmation
            yield {
                "event": "connected", 
                "data": json.dumps({
                    "type": "notification",
                    "method": "server/connected",
                    "params": {
                        "serverInfo": {
                            "name": "datasite-connector",
                            "version": "1.0.0"
                        }
                    }
                })
            }
            
            # Keep connection alive with periodic heartbeats
            while True:
                await asyncio.sleep(30)  # Send heartbeat every 30 seconds
                yield {
                    "event": "heartbeat", 
                    "data": json.dumps({
                        "type": "heartbeat",
                        "timestamp": asyncio.get_event_loop().time()
                    })
                }
        except asyncio.CancelledError:
            logger.info("SSE connection closed")
        except Exception as e:
            logger.error(f"Error in SSE stream: {e}")
    
    return EventSourceResponse(event_publisher())

@app.post("/")
async def handle_root_mcp(request: Request):
    """Handle MCP requests at root path."""
    logger.info(f"POST / called from {request.client}")
    return await handle_mcp_request(request)

@app.get("/")
async def root():
    """Root endpoint - return server info for discovery."""
    return {
        "name": "DataSite MCP Server",
        "version": "1.0.0",
        "protocol": "MCP Streamable HTTP",
        "transport": "streamable-http",
        "capabilities": {
            "tools": {}
        }
    }

@app.api_route("/{full_path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"])
async def catch_all(full_path: str, request: Request):
    """Catch-all route to log any requests we don't handle."""
    logger.warning(f"Unhandled {request.method} /{full_path} from {request.client}")
    logger.warning(f"Headers: {dict(request.headers)}")
    if request.method == "POST":
        try:
            body = await request.json()
            logger.warning(f"Body: {body}")
        except:
            pass
    return {"error": "endpoint not found", "path": full_path, "method": request.method}

@app.get("/openapi")
async def openapi_spec():
    """OpenAPI spec endpoint."""
    return {
        "openapi": "3.0.0",
        "info": {
            "title": "DataSite Connector",
            "description": "Access to private DataSite content with encrypted proprietary essays and documents",
            "version": "1.0.0"
        },
        "servers": [
            {
                "url": "https://ffdfe31a5750.ngrok-free.app",
                "description": "DataSite API Server"
            }
        ],
        "paths": {
            "/datasets": {
                "get": {
                    "summary": "List available datasets",
                    "description": "Get a list of all datasets available in the private datasite",
                    "responses": {
                        "200": {
                            "description": "List of available datasets",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "success": {"type": "boolean"},
                                            "datasets": {
                                                "type": "array",
                                                "items": {
                                                    "type": "object",
                                                    "properties": {
                                                        "name": {"type": "string"},
                                                        "description": {"type": "string"},
                                                        "content_type": {"type": "string"},
                                                        "size": {"type": "integer"},
                                                        "tags": {"type": "array", "items": {"type": "string"}}
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            },
            "/content": {
                "post": {
                    "summary": "Get content from dataset", 
                    "description": "Retrieve content from a specific dataset",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "dataset_name": {"type": "string"}
                                    },
                                    "required": ["dataset_name"]
                                }
                            }
                        }
                    },
                    "responses": {
                        "200": {
                            "description": "Dataset content",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "success": {"type": "boolean"},
                                            "content": {"type": "string"}
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }

@app.get("/datasets")
async def list_datasets():
    """REST API endpoint to list datasets."""
    try:
        content_repo = app_components.get('content_repo')
        if not content_repo:
            raise HTTPException(status_code=500, detail="Content repository not initialized")
        
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
        
        return {"success": True, "datasets": dataset_list}
        
    except Exception as e:
        logger.error(f"Error listing datasets: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/content")
async def get_content(request: Request):
    """REST API endpoint to get content."""
    try:
        data = await request.json()
        dataset_name = data.get("dataset_name")
        if not dataset_name:
            raise HTTPException(status_code=400, detail="dataset_name is required")
        
        content_repo = app_components.get('content_repo')
        if not content_repo:
            raise HTTPException(status_code=500, detail="Content repository not initialized")
        
        content = await content_repo.get_content(dataset_name)
        if content:
            return {
                "success": True,
                "content": content.decode('utf-8', errors='ignore'),
                "dataset_name": dataset_name
            }
        else:
            raise HTTPException(status_code=404, detail="Dataset not found")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting content: {e}")
        raise HTTPException(status_code=500, detail=str(e))

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