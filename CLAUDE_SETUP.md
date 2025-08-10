# Setting Up Claude MCP Connection to Your DataSite

## Step 1: Test the MCP Server Locally

First, let's make sure your MCP server works:

```bash
cd /Users/matthewprewitt/datasite-connector
source venv/bin/activate
python start_mcp_server.py
```

This should start the MCP server. You can test it by typing a simple JSON-RPC message (but for now, just make sure it starts without errors).

## Step 2: Configure Claude Desktop

### Option A: Claude Desktop App Configuration

1. **Find Claude's config directory:**
   - On macOS: `~/Library/Application Support/Claude/`
   - Create this directory if it doesn't exist

2. **Copy the MCP configuration:**
   ```bash
   mkdir -p ~/Library/Application\ Support/Claude/
   cp /Users/matthewprewitt/datasite-connector/claude_mcp_config.json ~/Library/Application\ Support/Claude/claude_desktop_config.json
   ```

3. **Restart Claude Desktop** - The app needs to restart to pick up the new MCP server

### Option B: Manual Configuration

1. Open Claude Desktop
2. Go to Settings > Developer
3. Add MCP Server with these settings:
   - **Name:** `datasite-connector`
   - **Command:** `python`
   - **Args:** `["/Users/matthewprewitt/datasite-connector/start_mcp_server.py"]`
   - **Working Directory:** `/Users/matthewprewitt/datasite-connector`
   - **Environment:** 
     - `PYTHONPATH=/Users/matthewprewitt/datasite-connector`
     - `VIRTUAL_ENV=/Users/matthewprewitt/datasite-connector/venv`

## Step 3: Test the Connection

Once configured, you should be able to use these tools in Claude:

### Available Tools:
- **`list_datasets`** - See what content is available
- **`get_content`** - Retrieve your essay content
- **`search_content`** - Search within your content
- **`get_content_summary`** - Get privacy-preserving summaries

### Example Prompts:
1. **"Can you list the datasets available in my datasite?"**
2. **"Please retrieve the content of 'making_unmaking_world_language' dataset"**
3. **"Search my datasite content for information about 'Phoenician alphabet'"**
4. **"What does my essay say about the relationship between literacy and magic?"**

## Step 4: Verify It's Working

Try this conversation with Claude:

```
You: "Please use the list_datasets tool to see what content I have in my datasite."

Claude should respond with your essay metadata showing:
- Name: making_unmaking_world_language  
- Tags: linguistics, philosophy, alphabet, mysticism, proprietary, essay
- Description: Essay on the Phoenician alphabet...
```

## Troubleshooting

### If Claude can't find your MCP server:
1. Check that the config file is in the right location
2. Restart Claude Desktop completely
3. Check the paths in the configuration are correct
4. Make sure the virtual environment exists

### If you get permission errors:
```bash
chmod +x /Users/matthewprewitt/datasite-connector/start_mcp_server.py
```

### If you get import errors:
Make sure you're using the virtual environment:
```bash
cd /Users/matthewprewitt/datasite-connector
source venv/bin/activate
python start_mcp_server.py
```

## Security Notes

- Your content never leaves your local machine
- The MCP server only runs when Claude needs it
- All content access is logged and can be audited
- Content is served from encrypted storage

## What You Can Ask Claude

Once connected, you can ask Claude questions like:
- "Summarize my essay on the Phoenician alphabet"
- "What does my essay say about McLuhan's views on literacy?"
- "Find all references to mysticism in my content"
- "Explain the connection my essay makes between alphabets and magic"
- "What are the main arguments in my piece about writing systems?"

Your proprietary content will be accessible to Claude for analysis while remaining completely private and encrypted on your local system! 🔒✨