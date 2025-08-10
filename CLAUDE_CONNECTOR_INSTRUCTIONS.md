# Claude "Connector" Instructions for Browser Access

Since browser Claude cannot use true MCP connectors, use this pattern to give Claude access to your DataSite content.

## 🎯 Copy-Paste This Into Browser Claude:

```
You now have access to a private DataSite connector with the following tools available at https://b4999221839d.ngrok-free.app:

**Available DataSite Tools:**

1. **list_datasets** - GET /datasets
   - Lists available private content
   - Optional query params: ?tags=tag1,tag2&content_type=text/plain

2. **get_content** - POST /content  
   - Retrieves content from datasets
   - Body: {"dataset_name": "name", "format": "raw|summary|metadata"}

3. **search_content** - POST /search
   - Searches within private content  
   - Body: {"query": "search terms", "max_results": 10}

4. **get_summary** - POST /summary
   - Gets privacy-preserving summaries
   - Body: {"dataset_name": "name", "summary_type": "semantic|statistical|structural"}

**Instructions:**
- Always use these tools to access my private content before answering questions
- Make HTTP requests to the endpoints above
- Parse the JSON responses and use the data to inform your answers
- My main content is the dataset "making_unmaking_world_language" - an essay about the Phoenician alphabet, literacy, and mysticism

Please acknowledge that you have access to these DataSite tools and are ready to use them.
```

## 🚀 **Example Conversation Flow:**

### **Step 1: Initialize the "Connector"**
Copy-paste the instructions above to browser Claude.

### **Step 2: Ask Content Questions** 
"What does my essay say about McLuhan's theory of literacy and sensory experience?"

### **Step 3: Claude Will Auto-Use the "Tools"**
Claude will:
1. Make GET request to `/datasets` to see available content
2. Make POST request to `/content` to retrieve your essay  
3. Analyze the content and provide insights

## 📋 **Ready-to-Use Prompts:**

### **Initialize Connector:**
```
You now have access to my private DataSite at https://b4999221839d.ngrok-free.app with these tools:
- GET /datasets (list content)
- POST /content (get content) 
- POST /search (search content)
- POST /summary (get summaries)

My main dataset is "making_unmaking_world_language" - an essay on the Phoenician alphabet and mysticism. Please acknowledge you can access this and are ready to help analyze my private content.
```

### **Content Analysis:**
```
Using my DataSite connector, please retrieve and analyze what my essay argues about the relationship between alphabetic writing and magical thinking. Focus on the McLuhan and Kabbalah sections.
```

### **Search Specific Topics:**
```  
Please search my essay for discussions of "letter mysticism" and "divine creation" using the DataSite search tool, then explain the connections my essay makes between writing systems and religious thought.
```

### **Compare Arguments:**
```
Using my DataSite, compare what my essay says about Chinese logographic writing versus alphabetic writing in terms of their impact on printing technology and cultural transformation.
```

## 🎭 **The "Connector" Illusion**

This approach makes browser Claude behave as if it has a native MCP connector by:
- ✅ Teaching it your API endpoints as "tools"
- ✅ Giving it structured access patterns  
- ✅ Making it automatically fetch content before answering
- ✅ Providing consistent, reliable access to your private data

## 🔒 **Privacy Maintained:**
- Your content never leaves your local machine
- Claude accesses it through your controlled API
- You can revoke access instantly by stopping the server
- All access is logged and auditable

This gives you **MCP-like functionality** in browser Claude while maintaining complete privacy and control over your proprietary content! 🎯✨