#!/usr/bin/env python3
"""
Setup script for DataSite Connector.
Initializes the application with default configuration and generates keys.
"""

import os
import sys
from pathlib import Path
from cryptography.fernet import Fernet
import secrets
import yaml

def setup_directories():
    """Create required directories."""
    directories = [
        "keys",
        "data",
        "logs",
        "private_content",
        "~/datasite/private",
        "~/datasite/public"
    ]
    
    for directory in directories:
        path = Path(directory).expanduser()
        path.mkdir(parents=True, exist_ok=True)
        print(f"Created directory: {path}")

def generate_keys():
    """Generate encryption and JWT keys."""
    keys_dir = Path("keys")
    keys_dir.mkdir(exist_ok=True)
    
    # Generate content encryption key
    content_key_path = keys_dir / "content.key"
    if not content_key_path.exists():
        key = Fernet.generate_key()
        with open(content_key_path, "wb") as f:
            f.write(key)
        content_key_path.chmod(0o600)
        print(f"Generated content encryption key: {content_key_path}")
    
    # Generate JWT secret key
    jwt_key_path = keys_dir / "jwt_secret.key"
    if not jwt_key_path.exists():
        secret = secrets.token_urlsafe(32)
        with open(jwt_key_path, "w") as f:
            f.write(secret)
        jwt_key_path.chmod(0o600)
        print(f"Generated JWT secret key: {jwt_key_path}")

def create_default_config():
    """Create default configuration file."""
    config_path = Path("config.yaml")
    
    if config_path.exists():
        print("Configuration file already exists")
        return
    
    default_config = {
        "syftbox_datasite_path": str(Path.home() / "datasite"),
        "content_storage_path": "./private_content",
        "encryption_key_path": "./keys/content.key",
        "mcp_server_host": "localhost",
        "mcp_server_port": 8080,
        "mcp_server_name": "datasite-connector",
        "auth_token_expiry": 3600,
        "max_requests_per_minute": 60,
        "enable_differential_privacy": True,
        "privacy_epsilon": 1.0,
        "log_level": "INFO",
        "debug_mode": False
    }
    
    with open(config_path, "w") as f:
        yaml.dump(default_config, f, default_flow_style=False)
    
    print(f"Created default configuration: {config_path}")

def create_env_file():
    """Create .env file from example."""
    env_path = Path(".env")
    example_path = Path(".env.example")
    
    if not env_path.exists() and example_path.exists():
        env_path.write_text(example_path.read_text())
        print(f"Created environment file: {env_path}")

def main():
    """Main setup function."""
    print("Setting up DataSite Connector...")
    
    try:
        setup_directories()
        generate_keys()
        create_default_config()
        create_env_file()
        
        print("\n✓ Setup completed successfully!")
        print("\nNext steps:")
        print("1. Review and customize config.yaml")
        print("2. Install SyftBox if not already installed")
        print("3. Run the application with: ./run.sh")
        
    except Exception as e:
        print(f"Setup failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()