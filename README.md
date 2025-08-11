# DataSite Connector

A dual-source MCP (Model Context Protocol) server that enables Claude to securely access both encrypted private content and SyftBox datasite files.

## Overview

DataSite Connector provides Claude with secure access to:
- **Encrypted Private Content** - Locally stored, encrypted files with privacy protection
- **SyftBox Datasite Files** - Public files from your personal SyftBox datasite network
- **Privacy-Preserving Access** - Differential privacy and access controls for sensitive content

## Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Claude AI     │    │  MCP Server      │    │  Data Sources   │
│                 │◄──►│  (SSE Protocol)  │◄──►│                 │
│  - list_datasets│    │                  │    │  • Encrypted    │
│  - get_content  │    │  - Authentication│    │    Repository   │
│  - search_content│    │  - Privacy       │    │  • SyftBox      │
└─────────────────┘    │  - Dual Sources  │    │    Datasite     │
                       └──────────────────┘    └─────────────────┘
```

## Key Features

- **Dual-Source Access**: Serves content from both encrypted storage and SyftBox datasites
- **SSE MCP Protocol**: Uses Server-Sent Events for real-time Claude integration
- **Privacy Protection**: Differential privacy and encryption for sensitive content
- **Access Control**: JWT-based authentication and rate limiting
- **Real-time Connectivity**: Ngrok tunnel support for Claude browser integration

## Installation

### Prerequisites

- Python 3.12+
- SyftBox installation and personal datasite
- Virtual environment recommended

### Setup

1. **Clone and setup**:
```bash
git clone https://github.com/your-repo/datasite-connector.git
cd datasite-connector
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

2. **Configure paths**:
The system expects:
- SyftBox datasite at `~/datasite/datasites/youremail@domain.com/public/`
- Encrypted content in `./private_content/`
- Configuration in `config.yaml`

3. **Run the server**:
```bash
source venv/bin/activate
python sse_mcp_server.py
```

4. **Optional - Public access via ngrok**:
```bash
ngrok http 8082
# Use the provided https URL in Claude MCP settings
```

## Configuration

The system uses `src/config.py` for settings:

```python
# Key settings in Config class:
syftbox_datasite_path: Path = Path.home() / "datasite"  # Your SyftBox path
content_storage_path: Path = Path("./private_content")   # Encrypted content
encryption_key_path: Path = Path("./keys/content.key")   # Encryption key
enable_differential_privacy: bool = True                 # Privacy protection
```

## MCP Tools Available to Claude

### `list_datasets`
Lists all available datasets from both sources:
- Encrypted private content (with metadata)
- SyftBox public files (from your personal datasite only)

### `get_content` 
Retrieves specific content by dataset name:
- First checks encrypted repository
- Falls back to SyftBox datasite files

### `search_content`
Searches across all content:
- Full-text search in encrypted content
- Filename matching in SyftBox files

## Data Sources

### 1. Encrypted Repository
- **Location**: `./private_content/`
- **Format**: JSON files with encrypted content and metadata
- **Features**: Differential privacy, access control, audit logging
- **Use case**: Sensitive proprietary content

### 2. SyftBox Datasite
- **Location**: `~/datasite/datasites/youremail@domain.com/public/`
- **Format**: Raw files (text, markdown, etc.)
- **Features**: Direct file access, public sharing ready
- **Use case**: Shareable research, documentation, public datasets

## Usage with Claude

1. **Start the server**:
```bash
python sse_mcp_server.py
```

2. **Connect Claude** (via MCP settings):
```json
{
  "mcpServers": {
    "datasite-connector": {
      "command": "curl",
      "args": ["-N", "https://your-ngrok-url.ngrok-free.app/sse"]
    }
  }
}
```

3. **Claude can now**:
- List all your datasets: `list_datasets`
- Read specific content: `get_content("filename")`
- Search across content: `search_content("query")`

## Project Structure

```
datasite-connector/
├── sse_mcp_server.py          # Main SSE MCP server
├── requirements.txt           # Python dependencies  
├── config.yaml               # Configuration overrides
├── src/
│   ├── config.py             # Configuration management
│   ├── datasite_manager.py   # SyftBox integration
│   ├── content_repository.py # Encrypted content handling
│   └── access_control.py     # Authentication & privacy
├── private_content/          # Encrypted content storage
├── keys/                     # Encryption keys (auto-generated)
└── venv/                     # Virtual environment
```

## Privacy & Security

### Data Sovereignty
- All data remains on your local system
- No data transmitted without explicit access
- Full control over content exposure

### Encryption
- AES encryption for private content
- Secure key generation and storage
- Content integrity verification

### Differential Privacy
- Optional noise injection for statistical privacy
- Configurable epsilon parameters
- Privacy-preserving content summaries

### Access Control
- JWT-based authentication
- Rate limiting and usage tracking
- Comprehensive audit logging

## Development

### Running the Server
```bash
# Development mode
source venv/bin/activate
python sse_mcp_server.py

# The server runs on http://0.0.0.0:8082
# Use ngrok for public access if needed
```

### Adding Content

**Encrypted Content** (programmatically):
```python
from src.content_repository import ContentRepository
from src.config import Config

config = Config()
repo = ContentRepository(config)
await repo.store_content("dataset_name", content_bytes, metadata)
```

**SyftBox Content** (direct file placement):
```bash
# Place files directly in your SyftBox public directory
cp myfile.txt ~/datasite/datasites/youremail@domain.com/public/
```

## Troubleshooting

### Common Issues

1. **"Datasites path does not exist"**
   - Check SyftBox installation and your email directory exists
   - Verify path: `~/datasite/datasites/youremail@domain.com/`

2. **"Connection refused"**
   - Ensure server is running on port 8082
   - Check firewall settings
   - Use ngrok for external access

3. **"No datasets found"**
   - Add content to `./private_content/` or SyftBox public directory
   - Check file permissions and encryption keys

### Debug Mode
Enable debug logging in `src/config.py`:
```python
debug_mode: bool = True
log_level: str = "DEBUG"
```

## License

This project is not yet licensed.

## Support

- Issues: Create GitHub issues for bugs and feature requests
- SyftBox: Check [SyftBox documentation](https://syftbox.openmined.org/)
- MCP: Review [Claude MCP documentation](https://docs.anthropic.com/en/docs/build-with-claude/mcp)