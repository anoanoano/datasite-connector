#!/usr/bin/env python3
"""
DataSite Connector - Main Entry Point

A SyftBox-based application that enables private content sharing
through Claude MCP connectors with privacy-preserving access controls.
"""

import asyncio
import logging
from pathlib import Path
from typing import Optional

from src.datasite_manager import DataSiteManager
from src.mcp_server import MCPServer
from src.content_repository import ContentRepository
from src.access_control import AccessControlSystem
from src.config import Config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class DataSiteConnectorApp:
    """Main application class for the DataSite Connector."""
    
    def __init__(self):
        self.config = Config()
        self.datasite_manager: Optional[DataSiteManager] = None
        self.content_repo: Optional[ContentRepository] = None
        self.access_control: Optional[AccessControlSystem] = None
        self.mcp_server: Optional[MCPServer] = None
    
    async def initialize(self) -> bool:
        """Initialize all application components."""
        try:
            logger.info("Initializing DataSite Connector...")
            
            # Initialize core components
            self.datasite_manager = DataSiteManager(self.config)
            await self.datasite_manager.initialize()
            
            self.content_repo = ContentRepository(self.config)
            await self.content_repo.initialize()
            
            self.access_control = AccessControlSystem(self.config)
            await self.access_control.initialize()
            
            # Initialize MCP server
            self.mcp_server = MCPServer(
                content_repo=self.content_repo,
                access_control=self.access_control,
                config=self.config
            )
            
            logger.info("DataSite Connector initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize DataSite Connector: {e}")
            return False
    
    async def run(self):
        """Run the main application loop."""
        if not await self.initialize():
            return
        
        try:
            logger.info("Starting DataSite Connector services...")
            
            # Start MCP server
            await self.mcp_server.start()
            
            # Run datasite monitoring and maintenance
            await self.datasite_manager.run_monitoring()
            
        except KeyboardInterrupt:
            logger.info("Received shutdown signal")
        except Exception as e:
            logger.error(f"Application error: {e}")
        finally:
            await self.cleanup()
    
    async def cleanup(self):
        """Clean up resources."""
        logger.info("Cleaning up resources...")
        
        if self.mcp_server:
            await self.mcp_server.stop()
        
        if self.datasite_manager:
            await self.datasite_manager.cleanup()
        
        logger.info("Cleanup completed")

def main():
    """Main entry point."""
    app = DataSiteConnectorApp()
    
    try:
        asyncio.run(app.run())
    except KeyboardInterrupt:
        logger.info("Application terminated by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())