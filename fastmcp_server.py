#!/usr/bin/env python3
"""
FastMCP Server using official Python SDK
"""
import asyncio
import logging
import json
from mcp.server.fastmcp import FastMCP

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
        logger.info("Initializing DataSite components for FastMCP server...")
        
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

# Create FastMCP server
mcp = FastMCP("datasite-connector")

@mcp.tool()
async def list_datasets(tags: list[str] = None) -> str:
    """List all available datasets in the datasite.
    
    Args:
        tags: Optional list of tags to filter by
        
    Returns:
        JSON string of available datasets
    """
    try:
        logger.info(f"FastMCP list_datasets called with tags: {tags}")
        
        content_repo = app_components.get('content_repo')
        if not content_repo:
            raise Exception("Content repository not initialized")
        
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
        return json.dumps(result, indent=2)
        
    except Exception as e:
        logger.error(f"Error in list_datasets: {e}")
        error_result = {"success": False, "error": str(e)}
        return json.dumps(error_result, indent=2)

@mcp.tool()
async def get_content(dataset_name: str) -> str:
    """Retrieve content from a specific dataset.
    
    Args:
        dataset_name: Name of the dataset to retrieve
        
    Returns:
        JSON string containing the dataset content
    """
    try:
        logger.info(f"FastMCP get_content called for dataset: {dataset_name}")
        
        content_repo = app_components.get('content_repo')
        if not content_repo:
            raise Exception("Content repository not initialized")
        
        content = await content_repo.get_content(dataset_name)
        if content:
            result = {
                "success": True,
                "content": content.decode('utf-8', errors='ignore'),
                "dataset_name": dataset_name
            }
        else:
            result = {"success": False, "error": "Dataset not found"}
            
        return json.dumps(result, indent=2)
        
    except Exception as e:
        logger.error(f"Error in get_content: {e}")
        error_result = {"success": False, "error": str(e)}
        return json.dumps(error_result, indent=2)

@mcp.tool()
async def search_content(query: str) -> str:
    """Search for content across all datasets.
    
    Args:
        query: Search query string
        
    Returns:
        JSON string of search results
    """
    try:
        logger.info(f"FastMCP search_content called with query: {query}")
        
        content_repo = app_components.get('content_repo')
        if not content_repo:
            raise Exception("Content repository not initialized")
        
        results = await content_repo.search_content(query=query)
        result = {"success": True, "results": results}
        return json.dumps(result, indent=2)
        
    except Exception as e:
        logger.error(f"Error in search_content: {e}")
        error_result = {"success": False, "error": str(e)}
        return json.dumps(error_result, indent=2)

async def main():
    """Main server function."""
    # Initialize components first
    await initialize_components()
    
    logger.info("Starting FastMCP server...")
    
    # Run the FastMCP server
    await mcp.run()

if __name__ == "__main__":
    asyncio.run(main())