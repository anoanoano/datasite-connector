"""
DataSite Manager - SyftBox integration and datasite management.
"""

import asyncio
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import yaml

try:
    from syftbox.lib import Client, SyftPermission
except ImportError:
    # Mock for development without SyftBox installed
    class Client:
        @classmethod
        def load(cls): return cls()
        
        @property
        def email(self): return "user@example.com"
    
    class SyftPermission:
        @staticmethod
        def datasite_default(email): pass

from .config import Config

logger = logging.getLogger(__name__)

@dataclass
class DatasetMetadata:
    """Metadata for a private dataset."""
    name: str
    description: str
    content_type: str
    size: int
    created_at: str
    tags: List[str]
    access_level: str
    owner_email: str

class DataSiteManager:
    """Manages SyftBox datasite operations and content organization."""
    
    def __init__(self, config: Config):
        self.config = config
        self.client: Optional[Client] = None
        self.datasets: Dict[str, DatasetMetadata] = {}
        self.private_path: Optional[Path] = None
        self.public_path: Optional[Path] = None
        
    async def initialize(self) -> None:
        """Initialize the SyftBox datasite."""
        try:
            logger.info("Initializing SyftBox datasite...")
            
            # Ensure directories exist
            self.config.ensure_directories()
            
            # Load SyftBox client
            self.client = Client.load()
            logger.info(f"Loaded SyftBox client for: {self.client.email}")
            
            # Set up datasite structure
            await self._setup_datasite_structure()
            
            # Load existing datasets
            await self._load_dataset_metadata()
            
            logger.info("DataSite manager initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize DataSite manager: {e}")
            raise
    
    async def _setup_datasite_structure(self) -> None:
        """Set up the datasite directory structure."""
        datasite_path = self.config.syftbox_datasite_path
        
        # Create standard datasite directories
        self.private_path = datasite_path / "private"
        self.public_path = datasite_path / "public"
        
        directories = [
            self.private_path,
            self.public_path,
            self.private_path / "content",
            self.private_path / "datasets",
            self.public_path / "results",
            self.public_path / "metadata",
        ]
        
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
            logger.debug(f"Created directory: {directory}")
        
        # Set default permissions
        if self.client:
            try:
                # Try newer API first
                SyftPermission.datasite_default(self.client.email)
            except TypeError:
                try:
                    # Try without parameters
                    SyftPermission.datasite_default()
                except:
                    # If permissions don't work, continue without them
                    logger.warning("Could not set datasite permissions")
    
    async def _load_dataset_metadata(self) -> None:
        """Load metadata for existing datasets."""
        metadata_path = self.public_path / "metadata"
        
        for metadata_file in metadata_path.glob("*.yaml"):
            try:
                with open(metadata_file, "r") as f:
                    data = yaml.safe_load(f)
                
                dataset_meta = DatasetMetadata(**data)
                self.datasets[dataset_meta.name] = dataset_meta
                logger.debug(f"Loaded dataset metadata: {dataset_meta.name}")
                
            except Exception as e:
                logger.warning(f"Failed to load metadata from {metadata_file}: {e}")
    
    async def add_content(self, name: str, content: bytes, 
                         content_type: str, description: str = "",
                         tags: List[str] = None) -> str:
        """Add proprietary content to the datasite."""
        if tags is None:
            tags = []
            
        try:
            logger.info(f"Adding content: {name}")
            
            # Store content in private directory
            content_path = self.private_path / "content" / name
            content_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(content_path, "wb") as f:
                f.write(content)
            
            # Create dataset metadata
            metadata = DatasetMetadata(
                name=name,
                description=description,
                content_type=content_type,
                size=len(content),
                created_at=asyncio.get_event_loop().time(),
                tags=tags,
                access_level="private",
                owner_email=self.client.email if self.client else "unknown"
            )
            
            # Save metadata to public directory (for discovery)
            await self._save_dataset_metadata(metadata)
            
            self.datasets[name] = metadata
            logger.info(f"Successfully added content: {name}")
            
            return str(content_path)
            
        except Exception as e:
            logger.error(f"Failed to add content {name}: {e}")
            raise
    
    async def _save_dataset_metadata(self, metadata: DatasetMetadata) -> None:
        """Save dataset metadata to public directory."""
        metadata_path = self.public_path / "metadata" / f"{metadata.name}.yaml"
        
        # Create dataset.yaml for SyftBox discovery
        metadata_dict = {
            "name": metadata.name,
            "description": metadata.description,
            "content_type": metadata.content_type,
            "size": metadata.size,
            "created_at": metadata.created_at,
            "tags": metadata.tags,
            "access_level": metadata.access_level,
            "owner_email": metadata.owner_email,
        }
        
        with open(metadata_path, "w") as f:
            yaml.dump(metadata_dict, f, default_flow_style=False)
        
        logger.debug(f"Saved metadata for: {metadata.name}")
    
    async def get_content(self, name: str) -> Optional[bytes]:
        """Retrieve content from the datasite."""
        try:
            content_path = self.private_path / "content" / name
            
            if not content_path.exists():
                logger.warning(f"Content not found: {name}")
                return None
            
            with open(content_path, "rb") as f:
                return f.read()
                
        except Exception as e:
            logger.error(f"Failed to retrieve content {name}: {e}")
            return None
    
    async def list_datasets(self) -> Dict[str, DatasetMetadata]:
        """List all available datasets."""
        return self.datasets.copy()
    
    async def remove_content(self, name: str) -> bool:
        """Remove content from the datasite."""
        try:
            content_path = self.private_path / "content" / name
            metadata_path = self.public_path / "metadata" / f"{name}.yaml"
            
            # Remove files
            if content_path.exists():
                content_path.unlink()
            
            if metadata_path.exists():
                metadata_path.unlink()
            
            # Remove from memory
            if name in self.datasets:
                del self.datasets[name]
            
            logger.info(f"Removed content: {name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to remove content {name}: {e}")
            return False
    
    async def run_monitoring(self) -> None:
        """Run continuous monitoring and maintenance tasks."""
        logger.info("Starting datasite monitoring...")
        
        try:
            while True:
                # Perform periodic maintenance
                await self._perform_maintenance()
                
                # Sleep for 5 minutes
                await asyncio.sleep(300)
                
        except asyncio.CancelledError:
            logger.info("Monitoring cancelled")
        except Exception as e:
            logger.error(f"Monitoring error: {e}")
    
    async def _perform_maintenance(self) -> None:
        """Perform periodic maintenance tasks."""
        logger.debug("Performing datasite maintenance...")
        
        # Reload dataset metadata in case of external changes
        await self._load_dataset_metadata()
        
        # Clean up orphaned files
        await self._cleanup_orphaned_files()
    
    async def _cleanup_orphaned_files(self) -> None:
        """Clean up files without corresponding metadata."""
        try:
            content_dir = self.private_path / "content"
            metadata_dir = self.public_path / "metadata"
            
            # Get list of content files
            content_files = {f.name for f in content_dir.iterdir() if f.is_file()}
            
            # Get list of metadata files
            metadata_files = {f.stem for f in metadata_dir.glob("*.yaml")}
            
            # Find orphaned content files
            orphaned = content_files - metadata_files
            
            for orphan in orphaned:
                orphan_path = content_dir / orphan
                logger.warning(f"Removing orphaned content file: {orphan}")
                orphan_path.unlink()
                
        except Exception as e:
            logger.error(f"Failed to cleanup orphaned files: {e}")
    
    async def cleanup(self) -> None:
        """Clean up resources."""
        logger.info("Cleaning up DataSite manager...")
        # Cleanup tasks if needed