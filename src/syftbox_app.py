"""
SyftBox App integration for DataSite Connector MCP.

This module handles the SyftBox App lifecycle and provides proper
identity management for accessing private datasites.
"""

import logging
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
import json
import yaml
from datetime import datetime, timedelta

from syftbox.lib import Client, SyftPermission
from syftbox.lib.permissions import (
    get_computed_permission, 
    PermissionType,
    PermissionRule
)

logger = logging.getLogger(__name__)

@dataclass
class AppSession:
    """Represents a session for a Claude user through the SyftBox App."""
    session_id: str
    user_email: str
    client_identifier: str  # e.g., "claude-workspace-123"
    created_at: datetime
    last_active: datetime
    permissions_cache: Dict[str, PermissionType]
    
    def is_expired(self, timeout_hours: int = 24) -> bool:
        """Check if session has expired."""
        return datetime.now() - self.last_active > timedelta(hours=timeout_hours)
    
    def touch(self) -> None:
        """Update last active time."""
        self.last_active = datetime.now()


class SyftBoxApp:
    """
    SyftBox App implementation for DataSite Connector.
    
    This class manages the app's identity, permissions, and provides
    a proxy layer for Claude users to access SyftBox datasites.
    """
    
    def __init__(self, app_config_path: Optional[Path] = None):
        """Initialize the SyftBox App."""
        self.app_config_path = app_config_path or Path("app.yaml")
        self.app_config = self._load_app_config()
        self.client: Optional[Client] = None
        self.sessions: Dict[str, AppSession] = {}
        self.app_identity: Optional[str] = None
        
    def _load_app_config(self) -> Dict[str, Any]:
        """Load app configuration from app.yaml."""
        try:
            if self.app_config_path.exists():
                with open(self.app_config_path, 'r') as f:
                    return yaml.safe_load(f)
            else:
                logger.warning(f"App config not found at {self.app_config_path}")
                return {}
        except Exception as e:
            logger.error(f"Failed to load app config: {e}")
            return {}
    
    async def initialize(self) -> bool:
        """
        Initialize the SyftBox App and establish identity.
        
        Returns:
            bool: True if initialization successful
        """
        try:
            logger.info("Initializing SyftBox App...")
            
            # Load SyftBox client
            self.client = Client.load()
            self.app_identity = f"{self.app_config['name']}@{self.client.email}"
            
            logger.info(f"SyftBox App initialized with identity: {self.app_identity}")
            logger.info(f"Running on datasite: {self.client.email}")
            
            # Set up app permissions file if it doesn't exist
            await self._setup_app_permissions()
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize SyftBox App: {e}")
            return False
    
    async def _setup_app_permissions(self) -> None:
        """
        Set up the app's permission configuration.
        
        Creates a syftperm.yaml file for the app if it doesn't exist.
        """
        try:
            # App's permission file location
            app_perm_path = self.client.my_datasite / "apps" / self.app_config['name'] / "syftperm.yaml"
            app_perm_path.parent.mkdir(parents=True, exist_ok=True)
            
            if not app_perm_path.exists():
                # Create default permission configuration for the app
                permissions_config = {
                    "version": "1.0",
                    "permissions": [
                        {
                            "path": "**",
                            "user": self.client.email,
                            "permissions": ["admin"]  # App owner has admin rights
                        }
                    ]
                }
                
                with open(app_perm_path, 'w') as f:
                    yaml.dump(permissions_config, f)
                
                logger.info(f"Created app permissions file at {app_perm_path}")
                
        except Exception as e:
            logger.warning(f"Could not set up app permissions: {e}")
    
    async def create_session(self, user_email: str, client_identifier: str) -> str:
        """
        Create a new session for a Claude user.
        
        Args:
            user_email: Email of the user requesting access
            client_identifier: Unique identifier for the Claude instance
            
        Returns:
            str: Session ID
        """
        import uuid
        
        session_id = str(uuid.uuid4())
        session = AppSession(
            session_id=session_id,
            user_email=user_email,
            client_identifier=client_identifier,
            created_at=datetime.now(),
            last_active=datetime.now(),
            permissions_cache={}
        )
        
        self.sessions[session_id] = session
        logger.info(f"Created session {session_id} for user {user_email}")
        
        return session_id
    
    async def check_permission(
        self, 
        session_id: str, 
        datasite_path: Path,
        permission_needed: PermissionType = PermissionType.READ
    ) -> bool:
        """
        Check if a session has permission to access a path.
        
        This is where the proxy magic happens - we check if:
        1. The session is valid
        2. The user has granted our app permission to act on their behalf
        3. The user has permission to access the requested resource
        
        Args:
            session_id: Session ID
            datasite_path: Path to check permission for
            permission_needed: Type of permission needed
            
        Returns:
            bool: True if permission granted
        """
        try:
            # Get session
            session = self.sessions.get(session_id)
            if not session:
                logger.warning(f"Invalid session: {session_id}")
                return False
            
            # Check if session expired
            if session.is_expired():
                logger.warning(f"Session expired: {session_id}")
                del self.sessions[session_id]
                return False
            
            session.touch()
            
            # Check cache first
            cache_key = f"{datasite_path}:{permission_needed}"
            if cache_key in session.permissions_cache:
                return session.permissions_cache[cache_key] >= permission_needed
            
            # Check actual permissions using SyftBox
            has_permission = await self._check_syftbox_permission(
                session.user_email,
                datasite_path,
                permission_needed
            )
            
            # Cache the result
            if has_permission:
                session.permissions_cache[cache_key] = permission_needed
            
            return has_permission
            
        except Exception as e:
            logger.error(f"Error checking permission: {e}")
            return False
    
    async def _check_syftbox_permission(
        self,
        user_email: str,
        datasite_path: Path,
        permission_needed: PermissionType
    ) -> bool:
        """
        Check SyftBox permissions for a user on a path.
        
        Args:
            user_email: User to check permissions for
            datasite_path: Path to check
            permission_needed: Permission level needed
            
        Returns:
            bool: True if permission granted
        """
        try:
            # For the app owner, always grant permission to their own datasite
            if user_email == self.client.email:
                logger.info(f"Owner access granted for {user_email}")
                return True
            
            # Get the snapshot folder (SyftBox root)
            snapshot_folder = self.client.my_datasite.parent.parent
            
            # Calculate relative path
            try:
                relative_path = datasite_path.relative_to(snapshot_folder)
            except ValueError:
                # Path is not under snapshot folder
                logger.warning(f"Path {datasite_path} not under SyftBox root")
                return False
            
            # Check computed permissions
            computed_perm = get_computed_permission(
                snapshot_folder=snapshot_folder,
                user_email=user_email,
                path=relative_path
            )
            
            # Check if user has required permission level
            has_permission = computed_perm.permission >= permission_needed
            
            if has_permission:
                logger.info(f"Permission granted for {user_email} on {relative_path}: {computed_perm.permission}")
            else:
                logger.warning(f"Permission denied for {user_email} on {relative_path}: {computed_perm.permission} < {permission_needed}")
            
            return has_permission
            
        except Exception as e:
            logger.error(f"Error checking SyftBox permission: {e}")
            # Fall back to ownership check
            return user_email == self.client.email
    
    async def list_accessible_datasites(self, session_id: str) -> List[Dict[str, Any]]:
        """
        List all datasites accessible to a session.
        
        Args:
            session_id: Session ID
            
        Returns:
            List of accessible datasites with metadata
        """
        accessible = []
        
        session = self.sessions.get(session_id)
        if not session:
            return accessible
        
        # Check all datasites
        datasites_path = self.client.my_datasite.parent
        
        for datasite_dir in datasites_path.iterdir():
            if datasite_dir.is_dir() and "@" in datasite_dir.name:
                # Check if user has permission to this datasite
                if await self.check_permission(session_id, datasite_dir):
                    accessible.append({
                        "email": datasite_dir.name,
                        "path": str(datasite_dir),
                        "has_public": (datasite_dir / "public").exists(),
                        "has_private": (datasite_dir / "private").exists()
                    })
        
        return accessible
    
    async def cleanup_expired_sessions(self) -> int:
        """
        Clean up expired sessions.
        
        Returns:
            int: Number of sessions cleaned up
        """
        expired = []
        for session_id, session in self.sessions.items():
            if session.is_expired():
                expired.append(session_id)
        
        for session_id in expired:
            del self.sessions[session_id]
            logger.info(f"Cleaned up expired session: {session_id}")
        
        return len(expired)
    
    def get_app_info(self) -> Dict[str, Any]:
        """
        Get information about the app.
        
        Returns:
            Dict with app information
        """
        return {
            "name": self.app_config.get("name", "unknown"),
            "version": self.app_config.get("version", "unknown"),
            "identity": self.app_identity,
            "author": self.app_config.get("author", "unknown"),
            "permissions_requested": self.app_config.get("permissions_requested", {}),
            "active_sessions": len(self.sessions),
            "client_email": self.client.email if self.client else None
        }