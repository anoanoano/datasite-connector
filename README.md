# DataSite Connector

A SyftBox-based application that enables privacy-preserving sharing of proprietary content through Claude MCP (Model Context Protocol) connectors.

## Overview

DataSite Connector allows you to:
- Set up a private datasite using OpenMined SyftBox
- Securely store proprietary content with end-to-end encryption
- Share content with Claude through MCP connectors while maintaining privacy
- Control access with granular permissions and audit trails
- Apply differential privacy techniques for additional protection

## Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Claude AI     │    │  MCP Connector   │    │  SyftBox        │
│                 │◄──►│                  │◄──►│  DataSite       │
│  - Queries      │    │  - Authentication│    │                 │
│  - Analysis     │    │  - Privacy       │    │  - Private      │
│  - Insights     │    │  - Rate Limiting │    │    Content      │
└─────────────────┘    └──────────────────┘    │  - Encryption   │
                                               │  - Access Ctrl  │
                                               └─────────────────┘
```

### Core Components

1. **DataSite Manager** - SyftBox integration and datasite management
2. **Content Repository** - Encrypted storage and retrieval of proprietary content
3. **MCP Server** - Claude Model Context Protocol server implementation
4. **Access Control System** - Authentication, authorization, and audit logging

## Installation

### Prerequisites

- Python 3.12+
- SyftBox installation
- Claude MCP support

### Setup

1. Clone this repository:
```bash
git clone https://github.com/anoanoano/datasite-connector.git
cd datasite-connector
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure SyftBox (if not already done):
```bash
# Follow SyftBox installation guide
curl -LsSf https://syftbox.openmined.org/install.sh | sh
```

4. Run the application:
```bash
./run.sh
```

## Configuration

Create a `config.yaml` file to customize settings:

```yaml
# SyftBox settings
syftbox_datasite_path: "~/datasite"

# Content repository
content_storage_path: "./private_content"
encryption_key_path: "./keys/content.key"

# MCP server
mcp_server_host: "localhost"
mcp_server_port: 8080
mcp_server_name: "datasite-connector"

# Privacy settings
enable_differential_privacy: true
privacy_epsilon: 1.0

# Access control
auth_token_expiry: 3600
max_requests_per_minute: 60
```

## Usage

### Adding Content

```python
from src.datasite_manager import DataSiteManager
from src.config import Config

config = Config()
manager = DataSiteManager(config)

# Add proprietary content
await manager.add_content(
    name="my_dataset",
    content=file_content,
    content_type="text/plain",
    description="My proprietary dataset",
    tags=["private", "research"]
)
```

### Creating Access Tokens

```python
from src.access_control import AccessControlSystem

access_control = AccessControlSystem(config)

# Create token for specific datasets
token = await access_control.create_access_token(
    user_email="user@example.com",
    datasets=["my_dataset"],
    permissions=["read"]
)
```

### Claude MCP Integration

Once running, Claude can access your content through the MCP interface:

```python
# Claude can call these tools:
# - list_datasets: Get available datasets
# - get_content: Retrieve specific content
# - search_content: Search across content
# - get_content_summary: Get privacy-preserving summaries
```

## Privacy Features

### Data Sovereignty
- All data remains on your local system
- No data leaves your datasite without explicit permission
- Full control over who can access what content

### Encryption
- End-to-end encryption of all proprietary content
- Secure key management with restricted file permissions
- Content integrity verification

### Differential Privacy
- Optional noise addition to protect individual data points
- Configurable privacy parameters (epsilon)
- Privacy-preserving summaries and statistics

### Access Control
- JWT-based authentication tokens
- Granular permissions per dataset
- Rate limiting and usage tracking
- Comprehensive audit logging

## Development

### Project Structure

```
datasite-connector/
├── main.py                 # Main application entry point
├── run.sh                  # SyftBox app runner script
├── requirements.txt        # Python dependencies
├── config.yaml            # Configuration file
├── src/
│   ├── __init__.py
│   ├── config.py          # Configuration management
│   ├── datasite_manager.py # SyftBox integration
│   ├── content_repository.py # Content storage
│   ├── mcp_server.py      # MCP server implementation
│   └── access_control.py   # Authentication & authorization
├── tests/                 # Test files
├── keys/                  # Encryption keys (auto-generated)
├── data/                  # Persistent data storage
└── dummy/                 # Temporary files
```

### Running Tests

```bash
pytest tests/
```

### Code Style

```bash
# Format code
black src/ tests/

# Check style
flake8 src/ tests/

# Type checking
mypy src/
```

## Security Considerations

- Keep encryption keys secure and backed up
- Regularly rotate access tokens
- Monitor audit logs for suspicious activity
- Use strong authentication for token creation
- Keep the system updated with security patches

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For questions and support:
- Create an issue on GitHub
- Check the SyftBox documentation
- Review the Claude MCP documentation

## Roadmap

- [ ] Web UI for content management
- [ ] Advanced privacy-preserving analytics
- [ ] Multi-user collaboration features
- [ ] Integration with more MCP clients
- [ ] Federated learning capabilities
- [ ] Mobile app support