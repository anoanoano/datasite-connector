#!/usr/bin/env python3
"""
HTTP API Server for DataSite Connector
Provides public API endpoints for browser-based Claude access
"""

import asyncio
import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime

from fastapi import FastAPI, HTTPException, Depends, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import uvicorn

from src.config import Config
from src.content_repository import ContentRepository
from src.datasite_manager import DataSiteManager
from src.access_control import AccessControlSystem

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="DataSite Connector API",
    description="HTTP API for accessing private DataSite content via Claude",
    version="1.0.0"
)

# Add CORS middleware for browser access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Be more restrictive in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Middleware to handle ngrok browser warning
@app.middleware("http")
async def handle_ngrok_warning(request: Request, call_next):
    """Handle ngrok browser warning by adding bypass headers to responses."""
    response = await call_next(request)
    
    # Add headers to help with ngrok access
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "*"
    
    # If this looks like an ngrok request, add bypass info to response
    if "ngrok" in str(request.url):
        # Add a note about ngrok bypass in the response
        if hasattr(response, 'body') and response.media_type == "application/json":
            try:
                import json
                body = json.loads(response.body)
                body["ngrok_info"] = "If you see a warning page, add header: ngrok-skip-browser-warning: true"
                response.body = json.dumps(body).encode()
            except:
                pass
    
    return response

# Global components
config = None
content_repo = None
datasite_manager = None
access_control = None

# Request models
class SearchRequest(BaseModel):
    query: str
    max_results: Optional[int] = 10

class ContentRequest(BaseModel):
    dataset_name: str
    format: Optional[str] = "raw"

class SummaryRequest(BaseModel):
    dataset_name: str
    summary_type: Optional[str] = "semantic"

class TokenRequest(BaseModel):
    user_email: str
    datasets: list[str]
    permissions: Optional[list[str]] = ["read"]
    expires_in: Optional[int] = 3600

# Response models
class APIResponse(BaseModel):
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    timestamp: str = datetime.now().isoformat()

@app.on_event("startup")
async def startup_event():
    """Initialize DataSite components on startup."""
    global config, content_repo, datasite_manager, access_control
    
    try:
        logger.info("Initializing DataSite Connector API...")
        
        config = Config()
        
        # Initialize components
        datasite_manager = DataSiteManager(config)
        await datasite_manager.initialize()
        
        content_repo = ContentRepository(config)
        await content_repo.initialize()
        
        access_control = AccessControlSystem(config)
        await access_control.initialize()
        
        logger.info("DataSite API initialized successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize DataSite API: {e}")
        raise

# Optional authentication (for production use)
async def get_api_key(x_api_key: Optional[str] = Header(None)):
    """Optional API key authentication."""
    # For now, allow all requests
    # In production, implement proper API key validation
    return x_api_key

@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "message": "DataSite Connector API",
        "version": "1.0.0",
        "endpoints": [
            "/datasets",
            "/content",
            "/search", 
            "/summary",
            "/health"
        ],
        "documentation": "/docs"
    }

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return APIResponse(
        success=True,
        data={
            "status": "healthy",
            "components": {
                "datasite_manager": datasite_manager is not None,
                "content_repo": content_repo is not None,
                "access_control": access_control is not None
            }
        }
    )

@app.get("/datasets")
async def list_datasets(
    tags: Optional[str] = None,
    content_type: Optional[str] = None,
    api_key: Optional[str] = Depends(get_api_key)
):
    """List available datasets."""
    try:
        tags_filter = tags.split(",") if tags else []
        
        datasets = await content_repo.list_datasets(
            tags_filter=tags_filter,
            content_type_filter=content_type
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
        
        return APIResponse(
            success=True,
            data={
                "datasets": dataset_list,
                "total_count": len(dataset_list)
            }
        )
        
    except Exception as e:
        logger.error(f"Error listing datasets: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/content")
async def get_content(
    request: ContentRequest,
    api_key: Optional[str] = Depends(get_api_key)
):
    """Get content from dataset."""
    try:
        dataset_name = request.dataset_name
        format_type = request.format
        
        if format_type == "metadata":
            metadata = await content_repo.get_metadata(dataset_name)
            if metadata:
                data = {
                    "name": metadata.name,
                    "description": metadata.description,
                    "content_type": metadata.content_type,
                    "size": metadata.size,
                    "tags": metadata.tags,
                    "created_at": metadata.created_at
                }
            else:
                raise HTTPException(status_code=404, detail="Dataset not found")
                
        elif format_type == "summary":
            summary = await content_repo.get_content_summary(
                dataset_name, summary_type="semantic"
            )
            data = {"summary": summary}
            
        else:  # raw format
            content = await content_repo.get_content(dataset_name)
            if content:
                try:
                    content_str = content.decode('utf-8')
                    data = {
                        "content": content_str,
                        "size": len(content),
                        "format": "text"
                    }
                except UnicodeDecodeError:
                    data = {
                        "content": f"[Binary content: {len(content)} bytes]",
                        "size": len(content),
                        "format": "binary",
                        "note": "Content is binary and cannot be displayed as text"
                    }
            else:
                raise HTTPException(status_code=404, detail="Content not found")
        
        return APIResponse(success=True, data=data)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting content: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/search")
async def search_content(
    request: SearchRequest,
    api_key: Optional[str] = Depends(get_api_key)
):
    """Search content in datasets."""
    try:
        results = await content_repo.search_content(
            query=request.query,
            max_results=request.max_results
        )
        
        return APIResponse(
            success=True,
            data={
                "results": results,
                "query": request.query,
                "result_count": len(results)
            }
        )
        
    except Exception as e:
        logger.error(f"Error searching content: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/summary")
async def get_content_summary(
    request: SummaryRequest,
    api_key: Optional[str] = Depends(get_api_key)
):
    """Get content summary."""
    try:
        summary = await content_repo.get_content_summary(
            request.dataset_name, 
            request.summary_type
        )
        
        if summary:
            return APIResponse(
                success=True,
                data={
                    "summary": summary,
                    "type": request.summary_type,
                    "dataset": request.dataset_name
                }
            )
        else:
            raise HTTPException(status_code=404, detail="Could not generate summary")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/tokens")
async def create_access_token(
    request: TokenRequest,
    api_key: Optional[str] = Depends(get_api_key)
):
    """Create access token (for future authentication)."""
    try:
        token = await access_control.create_access_token(
            user_email=request.user_email,
            datasets=request.datasets,
            permissions=request.permissions,
            expires_in=request.expires_in
        )
        
        return APIResponse(
            success=True,
            data={
                "token": token,
                "expires_in": request.expires_in,
                "datasets": request.datasets,
                "permissions": request.permissions
            }
        )
        
    except Exception as e:
        logger.error(f"Error creating token: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Error handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content=APIResponse(
            success=False,
            error=exc.detail
        ).dict()
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content=APIResponse(
            success=False,
            error="Internal server error"
        ).dict()
    )

def start_api_server(host: str = "0.0.0.0", port: int = 8080, dev: bool = True):
    """Start the API server."""
    logger.info(f"Starting DataSite API server on {host}:{port}")
    
    uvicorn.run(
        "api_server:app",
        host=host,
        port=port,
        reload=dev,
        log_level="info"
    )

if __name__ == "__main__":
    start_api_server()