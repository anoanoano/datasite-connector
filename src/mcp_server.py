"""
MCP Server - Claude Model Context Protocol server implementation.
"""

import asyncio
import json
import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from datetime import datetime

try:
    from mcp.server import Server
    from mcp.types import Tool, TextContent, ImageContent
except ImportError:
    # Mock for development
    class Server:
        def __init__(self, name: str): pass
        def list_tools(self): pass
        def call_tool(self, name: str, arguments: dict): pass
    
    @dataclass
    class Tool:
        name: str
        description: str
        inputSchema: dict
    
    class TextContent:
        def __init__(self, text: str): self.text = text
    
    class ImageContent:
        def __init__(self, data: str, mimeType: str): pass

from .config import Config
from .content_repository import ContentRepository
from .access_control import AccessControlSystem

logger = logging.getLogger(__name__)

@dataclass
class MCPResponse:
    """Standard MCP response format."""
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

class MCPServer:
    """Claude Model Context Protocol server for datasite content access."""
    
    def __init__(self, content_repo: ContentRepository, 
                 access_control: AccessControlSystem, config: Config):
        self.content_repo = content_repo
        self.access_control = access_control
        self.config = config
        self.server = Server(config.mcp_server_name)
        self.is_running = False
        
        # Register MCP tools
        self._register_tools()
    
    def _register_tools(self) -> None:
        """Register available MCP tools for Claude."""
        tools = [
            Tool(
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
            Tool(
                name="get_content",
                description="Retrieve specific content from the datasite",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "dataset_name": {
                            "type": "string",
                            "description": "Name of the dataset to retrieve"
                        },
                        "access_token": {
                            "type": "string",
                            "description": "Access token for authentication"
                        },
                        "format": {
                            "type": "string",
                            "enum": ["raw", "summary", "metadata"],
                            "description": "Format of the returned content"
                        }
                    },
                    "required": ["dataset_name"]
                }
            ),
            Tool(
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
                            "description": "Maximum number of results"
                        },
                        "access_token": {
                            "type": "string",
                            "description": "Access token for authentication"
                        }
                    },
                    "required": ["query"]
                }
            ),
            Tool(
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
                            "description": "Type of summary to generate"
                        }
                    },
                    "required": ["dataset_name"]
                }
            )
        ]
        
        # Store tools for later use (MCP server setup will be done differently)
        self.tools = tools
        logger.debug(f"Registered {len(tools)} MCP tools")
    
    async def _handle_tool_call(self, name: str, arguments: Dict[str, Any]) -> List[TextContent]:
        """Handle MCP tool calls from Claude."""
        try:
            logger.info(f"Handling tool call: {name} with args: {arguments}")
            
            # Route to appropriate handler
            if name == "list_datasets":
                response = await self._handle_list_datasets(arguments)
            elif name == "get_content":
                response = await self._handle_get_content(arguments)
            elif name == "search_content":
                response = await self._handle_search_content(arguments)
            elif name == "get_content_summary":
                response = await self._handle_get_content_summary(arguments)
            else:
                response = MCPResponse(
                    success=False,
                    error=f"Unknown tool: {name}"
                )
            
            # Return formatted response
            return [TextContent(json.dumps(asdict(response), indent=2))]
            
        except Exception as e:
            logger.error(f"Tool call error: {e}")
            error_response = MCPResponse(
                success=False,
                error=f"Internal error: {str(e)}"
            )
            return [TextContent(json.dumps(asdict(error_response), indent=2))]
    
    async def _handle_list_datasets(self, args: Dict[str, Any]) -> MCPResponse:
        """Handle list_datasets tool call."""
        try:
            # Extract filters
            tags_filter = args.get("tags", [])
            content_type_filter = args.get("content_type")
            
            # Get datasets from content repository
            datasets = await self.content_repo.list_datasets(
                tags_filter=tags_filter,
                content_type_filter=content_type_filter
            )
            
            # Convert to serializable format
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
            
            return MCPResponse(
                success=True,
                data=dataset_list,
                metadata={"total_count": len(dataset_list)}
            )
            
        except Exception as e:
            return MCPResponse(success=False, error=str(e))
    
    async def _handle_get_content(self, args: Dict[str, Any]) -> MCPResponse:
        """Handle get_content tool call."""
        try:
            dataset_name = args["dataset_name"]
            access_token = args.get("access_token")
            format_type = args.get("format", "raw")
            
            # Verify access permissions
            if access_token:
                has_access = await self.access_control.verify_access(
                    access_token, dataset_name
                )
                if not has_access:
                    return MCPResponse(
                        success=False,
                        error="Access denied: Invalid token or insufficient permissions"
                    )
            
            # Get content based on format
            if format_type == "metadata":
                metadata = await self.content_repo.get_metadata(dataset_name)
                if metadata:
                    return MCPResponse(
                        success=True,
                        data={
                            "name": metadata.name,
                            "description": metadata.description,
                            "content_type": metadata.content_type,
                            "size": metadata.size,
                            "tags": metadata.tags,
                            "created_at": metadata.created_at
                        }
                    )
                else:
                    return MCPResponse(
                        success=False,
                        error="Dataset not found"
                    )
            
            elif format_type == "summary":
                summary = await self.content_repo.get_content_summary(
                    dataset_name, summary_type="semantic"
                )
                return MCPResponse(success=True, data={"summary": summary})
            
            else:  # raw format
                content = await self.content_repo.get_content(dataset_name)
                if content:
                    # Apply differential privacy if enabled
                    if self.config.enable_differential_privacy:
                        content = await self._apply_differential_privacy(content)
                    
                    return MCPResponse(
                        success=True,
                        data={"content": content.decode('utf-8') if isinstance(content, bytes) else content}
                    )
                else:
                    return MCPResponse(
                        success=False,
                        error="Content not found"
                    )
            
        except Exception as e:
            return MCPResponse(success=False, error=str(e))
    
    async def _handle_search_content(self, args: Dict[str, Any]) -> MCPResponse:
        """Handle search_content tool call."""
        try:
            query = args["query"]
            max_results = args.get("max_results", 10)
            access_token = args.get("access_token")
            
            # Perform search
            results = await self.content_repo.search_content(
                query=query,
                max_results=max_results,
                access_token=access_token
            )
            
            return MCPResponse(
                success=True,
                data=results,
                metadata={"query": query, "result_count": len(results)}
            )
            
        except Exception as e:
            return MCPResponse(success=False, error=str(e))
    
    async def _handle_get_content_summary(self, args: Dict[str, Any]) -> MCPResponse:
        """Handle get_content_summary tool call."""
        try:
            dataset_name = args["dataset_name"]
            summary_type = args.get("summary_type", "semantic")
            
            summary = await self.content_repo.get_content_summary(
                dataset_name, summary_type
            )
            
            if summary:
                return MCPResponse(
                    success=True,
                    data={"summary": summary, "type": summary_type}
                )
            else:
                return MCPResponse(
                    success=False,
                    error="Could not generate summary"
                )
            
        except Exception as e:
            return MCPResponse(success=False, error=str(e))
    
    async def _apply_differential_privacy(self, content: bytes) -> bytes:
        """Apply differential privacy to content."""
        # Placeholder for differential privacy implementation
        # In a real implementation, this would add calibrated noise
        # based on the privacy epsilon parameter
        logger.debug("Applying differential privacy...")
        return content
    
    async def start(self) -> None:
        """Start the MCP server."""
        try:
            logger.info(f"Starting MCP server on {self.config.mcp_server_host}:{self.config.mcp_server_port}")
            
            # In a real implementation, this would start the MCP server
            # For now, we'll just mark it as running
            self.is_running = True
            
            logger.info("MCP server started successfully")
            
            # Keep the server running
            while self.is_running:
                await asyncio.sleep(1)
                
        except Exception as e:
            logger.error(f"Failed to start MCP server: {e}")
            raise
    
    async def stop(self) -> None:
        """Stop the MCP server."""
        logger.info("Stopping MCP server...")
        self.is_running = False
        logger.info("MCP server stopped")