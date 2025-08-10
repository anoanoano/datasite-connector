"""
Configuration management for DataSite Connector.
"""

import os
from pathlib import Path
from typing import Optional, Dict, Any
import yaml
from pydantic import Field
from pydantic_settings import BaseSettings

class Config(BaseSettings):
    """Application configuration settings."""
    
    # SyftBox settings
    syftbox_datasite_path: Path = Field(
        default_factory=lambda: Path.home() / "datasite",
        description="Path to SyftBox datasite directory"
    )
    
    # Content repository settings
    content_storage_path: Path = Field(
        default_factory=lambda: Path("./private_content"),
        description="Path to private content storage"
    )
    
    encryption_key_path: Path = Field(
        default_factory=lambda: Path("./keys/content.key"),
        description="Path to content encryption key"
    )
    
    # MCP server settings
    mcp_server_host: str = Field(default="localhost", description="MCP server host")
    mcp_server_port: int = Field(default=8080, description="MCP server port")
    mcp_server_name: str = Field(default="datasite-connector", description="MCP server name")
    
    # Access control settings
    auth_token_expiry: int = Field(default=3600, description="Auth token expiry in seconds")
    max_requests_per_minute: int = Field(default=60, description="Rate limit per minute")
    
    # Privacy settings
    enable_differential_privacy: bool = Field(default=True, description="Enable differential privacy")
    privacy_epsilon: float = Field(default=1.0, description="Differential privacy epsilon")
    
    # Logging settings
    log_level: str = Field(default="INFO", description="Logging level")
    log_file: Optional[Path] = Field(default=None, description="Log file path")
    
    # Development settings
    debug_mode: bool = Field(default=False, description="Enable debug mode")
    
    class Config:
        env_prefix = "DATASITE_"
        env_file = ".env"
    
    @classmethod
    def load_from_file(cls, config_path: Path) -> "Config":
        """Load configuration from YAML file."""
        if config_path.exists():
            with open(config_path, "r") as f:
                config_data = yaml.safe_load(f)
            return cls(**config_data)
        return cls()
    
    def save_to_file(self, config_path: Path) -> None:
        """Save configuration to YAML file."""
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, "w") as f:
            yaml.dump(self.dict(), f, default_flow_style=False)
    
    def get_syftbox_client_config(self) -> Dict[str, Any]:
        """Get SyftBox client configuration."""
        return {
            "datasite_path": str(self.syftbox_datasite_path),
            "debug": self.debug_mode,
        }
    
    def ensure_directories(self) -> None:
        """Ensure all required directories exist."""
        directories = [
            self.syftbox_datasite_path,
            self.content_storage_path,
            self.encryption_key_path.parent,
        ]
        
        for directory in directories:
            try:
                directory.mkdir(parents=True, exist_ok=True)
            except OSError as e:
                # If directory exists but we can't create it (read-only), that's okay
                if directory.exists():
                    continue
                else:
                    raise e