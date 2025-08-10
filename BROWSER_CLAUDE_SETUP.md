# Using Browser-Based Claude with Your DataSite

Yes! You can absolutely set up a public API endpoint for browser-based Claude access. Here's how:

## 🚀 **Method 1: Quick Start with ngrok (Recommended)**

### Step 1: Start Your API Server
```bash
cd /Users/matthewprewitt/datasite-connector
./start_public_api.sh
```

This starts your API server on `http://localhost:8080`

### Step 2: Install and Run ngrok
```bash
# Install ngrok (if not already installed)
brew install ngrok

# Create public tunnel to your API
ngrok http 8080
```

This will give you a public URL like: `https://abc123.ngrok.io`

### Step 3: Use in Browser Claude
Now you can ask browser-based Claude:

**"Please make a GET request to https://abc123.ngrok.io/datasets to list available datasets"**

**"Please make a POST request to https://abc123.ngrok.io/content with the JSON body `{\"dataset_name\": \"making_unmaking_world_language\", \"format\": \"raw\"}` to get my essay content"**

## 🔧 **Method 2: Direct Local Network Access**

If you're on the same network:

### Step 1: Find Your Local IP
```bash
ifconfig | grep "inet " | grep -v 127.0.0.1
```

### Step 2: Start API Server on All Interfaces
```bash
cd /Users/matthewprewitt/datasite-connector
source venv/bin/activate
python -c "from api_server import start_api_server; start_api_server(host='0.0.0.0', port=8080)"
```

### Step 3: Use Your Local IP
Use `http://YOUR_LOCAL_IP:8080` in browser Claude requests

## 📡 **Available API Endpoints**

Your API provides these endpoints for Claude:

### **GET /datasets**
List available datasets
- **URL**: `https://your-ngrok-url.ngrok.io/datasets`
- **Query params**: `?tags=linguistics,philosophy&content_type=text/plain`

### **POST /content**
Get content from dataset
- **URL**: `https://your-ngrok-url.ngrok.io/content`
- **Body**: `{\"dataset_name\": \"making_unmaking_world_language\", \"format\": \"raw\"}`

### **POST /search**
Search within content
- **URL**: `https://your-ngrok-url.ngrok.io/search`
- **Body**: `{\"query\": \"Phoenician alphabet\", \"max_results\": 10}`

### **POST /summary**
Get content summary
- **URL**: `https://your-ngrok-url.ngrok.io/summary`
- **Body**: `{\"dataset_name\": \"making_unmaking_world_language\", \"summary_type\": \"semantic\"}`

### **GET /health**
Check API health
- **URL**: `https://your-ngrok-url.ngrok.io/health`

## 🎯 **Example Claude Conversations**

Once your API is running publicly, try these with browser Claude:

### **1. List Your Content**
> "Please make a GET request to https://abc123.ngrok.io/datasets to see what content is available in my datasite"

### **2. Get Your Essay**
> "Please make a POST request to https://abc123.ngrok.io/content with the JSON body {\"dataset_name\": \"making_unmaking_world_language\", \"format\": \"raw\"} and then analyze the main arguments about the Phoenician alphabet"

### **3. Search Your Content**
> "Please search my datasite content by making a POST request to https://abc123.ngrok.io/search with {\"query\": \"McLuhan literacy\", \"max_results\": 5} and tell me what it finds about McLuhan's theory"

### **4. Get a Summary**
> "Please get a summary of my essay by POST to https://abc123.ngrok.io/summary with {\"dataset_name\": \"making_unmaking_world_language\", \"summary_type\": \"semantic\"}"

## 🔒 **Security Notes**

- Your content **remains encrypted** on your local machine
- The API provides **read-only access** to your content
- **No data is stored** on external servers
- The ngrok tunnel is **temporary** and closes when you stop it
- You can **revoke access** instantly by stopping the server

## 🛠 **Troubleshooting**

### API Won't Start
```bash
# Make sure you're in the right directory and virtual environment
cd /Users/matthewprewitt/datasite-connector
source venv/bin/activate
python api_server.py
```

### ngrok Issues
```bash
# If ngrok isn't installed
brew install ngrok

# If you need to authenticate ngrok
ngrok config add-authtoken YOUR_TOKEN
```

### CORS Issues
The API is configured to allow all origins for browser access. In production, you'd want to restrict this.

## 🎉 **Ready to Use!**

Your DataSite content is now accessible to browser-based Claude while remaining:
- ✅ **Completely private** (stored locally)
- ✅ **Encrypted at rest**
- ✅ **Under your control**
- ✅ **Audit logged**
- ✅ **Revocable instantly**

Browser Claude can now analyze your proprietary essay about the Phoenician alphabet! 📚✨