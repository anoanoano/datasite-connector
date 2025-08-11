#!/usr/bin/env python3
"""
MCP Server with HTTP+SSE Transport (2024-11-05 spec)
Following the exact pattern that works for Cloudflare
"""
import asyncio
import json
import logging
import uuid
from typing import Any, Dict, Optional

from fastapi import FastAPI, Request, HTTPException
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
        logger.info("Initializing DataSite components for SSE MCP server...")
        
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
    title="DataSite MCP Server (SSE)",
    description="MCP server for DataSite content access using HTTP+SSE transport",
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
    logger.info("SSE MCP list_tools called")
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
        logger.info(f"SSE MCP tool called: {name} with arguments: {arguments}")
        
        content_repo = app_components.get('content_repo')
        datasite_manager = app_components.get('datasite_manager')
        config = app_components.get('config')
        
        if not content_repo:
            raise Exception("Content repository not initialized")
        
        if name == "list_datasets":
            dataset_list = []
            
            # Get datasets from encrypted content repository
            datasets = await content_repo.list_datasets()
            for dataset_name, metadata in datasets.items():
                dataset_list.append({
                    "name": metadata.name,
                    "description": metadata.description,
                    "content_type": metadata.content_type,
                    "size": metadata.size,
                    "tags": metadata.tags,
                    "source": "encrypted_repo"
                })
            
            # Also scan SyftBox datasite public directory for files
            if config:
                syftbox_datasite_path = config.syftbox_datasite_path.expanduser().resolve()
                logger.info(f"Scanning SyftBox datasite path: {syftbox_datasite_path}")
                user_datasite_path = None
                
                # Find user's datasite directory
                datasites_path = syftbox_datasite_path / "datasites"
                logger.info(f"Looking for datasites in: {datasites_path}")
                if datasites_path.exists():
                    logger.info(f"Datasites path exists, looking for mtprewitt@gmail.com...")
                    user_datasite_path = datasites_path / "mtprewitt@gmail.com"
                    if user_datasite_path.exists():
                        logger.info(f"Found target user datasite: {user_datasite_path}")
                    else:
                        logger.warning(f"Target user datasite not found: {user_datasite_path}")
                        user_datasite_path = None
                else:
                    logger.warning(f"Datasites path does not exist: {datasites_path}")
                    user_datasite_path = None
                
                if user_datasite_path:
                    public_path = user_datasite_path / "public"
                    logger.info(f"Checking public path: {public_path}")
                    if public_path.exists():
                        logger.info(f"Public path exists, scanning files...")
                        for file_path in public_path.iterdir():
                            if file_path.is_file() and file_path.name != "syft.pub.yaml":
                                logger.info(f"Found SyftBox file: {file_path.name}")
                                # Add SyftBox files to dataset list
                                dataset_list.append({
                                    "name": file_path.name,
                                    "description": f"File from SyftBox datasite: {file_path.name}",
                                    "content_type": "text/plain",
                                    "size": file_path.stat().st_size,
                                    "tags": ["syftbox", "public"],
                                    "source": "syftbox_datasite"
                                })
                    else:
                        logger.warning(f"Public path does not exist: {public_path}")
                else:
                    logger.warning("No user datasite path found")
            
            result = {"success": True, "datasets": dataset_list}
        
        elif name == "get_content":
            dataset_name = arguments["dataset_name"]
            content = None
            
            # First try encrypted content repository
            content = await content_repo.get_content(dataset_name)
            
            # If not found, try SyftBox datasite
            if not content and config:
                syftbox_datasite_path = config.syftbox_datasite_path.expanduser().resolve()
                datasites_path = syftbox_datasite_path / "datasites"
                
                if datasites_path.exists():
                    user_datasite_path = datasites_path / "mtprewitt@gmail.com"
                    if user_datasite_path.exists():
                        public_path = user_datasite_path / "public"
                        file_path = public_path / dataset_name
                        if file_path.exists() and file_path.is_file():
                            try:
                                with open(file_path, 'rb') as f:
                                    content = f.read()
                                logger.info(f"Found content in SyftBox datasite: {dataset_name}")
                            except Exception as e:
                                logger.error(f"Error reading SyftBox file {dataset_name}: {e}")
            
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
            
            # Also search in SyftBox datasite files
            if config:
                syftbox_datasite_path = config.syftbox_datasite_path.expanduser().resolve()
                datasites_path = syftbox_datasite_path / "datasites"
                
                if datasites_path.exists():
                    user_datasite_path = datasites_path / "mtprewitt@gmail.com"
                    if user_datasite_path.exists():
                        public_path = user_datasite_path / "public"
                        if public_path.exists():
                            for file_path in public_path.iterdir():
                                if file_path.is_file() and file_path.name != "syft.pub.yaml":
                                    # Simple filename and content search
                                    if query.lower() in file_path.name.lower():
                                        results.append({
                                            "name": file_path.name,
                                            "description": f"SyftBox file matching '{query}'",
                                            "content_type": "text/plain",
                                            "tags": ["syftbox", "public"],
                                            "relevance_score": 1.0
                                        })
            
            result = {"success": True, "results": results}
        
        else:
            result = {"success": False, "error": f"Unknown tool: {name}"}
        
        return [types.TextContent(
            type="text",
            text=json.dumps(result, indent=2)
        )]
        
    except Exception as e:
        logger.error(f"Error in SSE MCP tool call {name}: {e}")
        error_result = {"success": False, "error": str(e)}
        return [types.TextContent(
            type="text",
            text=json.dumps(error_result, indent=2)
        )]

# Session management for SSE connections
active_sessions = {}

class MCPSession:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.message_queue = asyncio.Queue()
        self.is_connected = False
        
    async def send_message(self, message: dict):
        """Send a message to the client via SSE."""
        await self.message_queue.put(message)

# HTTP+SSE Transport Implementation

# Remove POST /sse handler - Claude should get 405 to trigger SSE fallback

@app.get("/sse")
async def handle_sse_connection(request: Request):
    """Handle SSE connection from Claude."""
    session_id = str(uuid.uuid4())
    logger.info(f"New SSE connection established with session ID: {session_id}")
    
    # Create session
    session = MCPSession(session_id)
    active_sessions[session_id] = session
    session.is_connected = True
    
    async def event_generator():
        try:
            # First, send the endpoint event with the message URL including session ID
            endpoint_event = {
                "event": "endpoint", 
                "data": f"/messages?session_id={session_id}"
            }
            logger.info(f"Sending endpoint event: {endpoint_event}")
            yield endpoint_event
            
            # Send keep-alive pings every 15 seconds and handle messages
            while session.is_connected:
                try:
                    # Check for messages with timeout for keep-alive
                    message = await asyncio.wait_for(session.message_queue.get(), timeout=15.0)
                    
                    # Send message event
                    yield {
                        "event": "message",
                        "data": json.dumps(message)
                    }
                    
                except asyncio.TimeoutError:
                    # Send keep-alive ping
                    yield {
                        "event": "ping",
                        "data": json.dumps({"type": "ping", "timestamp": asyncio.get_event_loop().time()})
                    }
                    
        except asyncio.CancelledError:
            logger.info(f"SSE connection {session_id} cancelled")
        except Exception as e:
            logger.error(f"Error in SSE connection {session_id}: {e}")
        finally:
            # Clean up session
            if session_id in active_sessions:
                del active_sessions[session_id]
            logger.info(f"SSE connection {session_id} closed")
    
    return EventSourceResponse(event_generator())

@app.post("/messages")
async def handle_message_post(request: Request):
    """Handle POST messages from Claude."""
    try:
        data = await request.json()
        logger.info(f"Received POST message: {json.dumps(data, indent=2)}")
        
        # Extract session ID from query parameters
        session_id = request.query_params.get('session_id')
        if not session_id:
            logger.error("No session_id provided in query parameters")
            return JSONResponse(
                content={"error": "No session_id provided"},
                status_code=400
            )
        
        if session_id not in active_sessions:
            logger.error(f"Session {session_id} not found in active sessions")
            return JSONResponse(
                content={"error": "Invalid session_id"},
                status_code=400
            )
        
        session = active_sessions[session_id]
        
        method = data.get("method")
        params = data.get("params", {})
        request_id = data.get("id")
        
        if method == "initialize":
            logger.info(f"Initialize request with params: {params}")
            # Use the client's preferred protocol version
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
            logger.info(f"Sending initialize response via SSE: {json.dumps(response, indent=2)}")
            await session.send_message(response)
        
        elif method == "notifications/initialized":
            logger.info("Received notifications/initialized")
            # No response needed for notifications
        
        elif method == "tools/list":
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
            logger.info(f"Sending tools/list response via SSE: {json.dumps(response, indent=2)}")
            await session.send_message(response)
        
        elif method == "tools/call":
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
            logger.info(f"Sending tools/call response via SSE")
            await session.send_message(response)
        
        else:
            logger.warning(f"Unknown method: {method}")
            error_response = {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32601,
                    "message": f"Method not found: {method}"
                }
            }
            await session.send_message(error_response)
        
        # Return 204 No Content for POST /messages
        from fastapi import Response
        return Response(status_code=204)
        
    except Exception as e:
        logger.error(f"Error handling POST message: {e}")
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

# OAuth discovery endpoints (return 404 to indicate no OAuth support)
@app.get("/.well-known/oauth-protected-resource/sse")
async def oauth_protected_resource_sse():
    """Return 404 to indicate no OAuth support."""
    raise HTTPException(status_code=404, detail="OAuth not supported")

@app.get("/.well-known/oauth-authorization-server/sse")
async def oauth_authorization_server_sse():
    """Return 404 to indicate no OAuth support."""
    raise HTTPException(status_code=404, detail="OAuth not supported")

@app.get("/.well-known/oauth-authorization-server")
async def oauth_authorization_server():
    """Return 404 to indicate no OAuth support."""
    raise HTTPException(status_code=404, detail="OAuth not supported")

@app.post("/register")
async def oauth_register():
    """Return 404 to indicate no OAuth registration support."""
    raise HTTPException(status_code=404, detail="OAuth registration not supported")

@app.head("/sse")
async def handle_sse_head():
    """Handle HEAD requests to SSE endpoint."""
    from fastapi import Response
    return Response(headers={
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive"
    })

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