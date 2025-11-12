# Semantic Kernel Migration - chat_app_sk.py

## Overview
Created a new FastAPI chat application (`chat_app_sk.py`) that uses **Semantic Kernel's HandoffOrchestration** instead of the custom handoff logic in the original `chat_app.py`.

## Key Differences from Original chat_app.py

### 1. **Agent Framework**
- **Original**: Custom agent management with Azure AI Projects SDK
- **New**: Semantic Kernel's HandoffOrchestration for agent-to-agent handoffs

### 2. **Handoff Logic**
- **Original**: Manual handoff decision using GPT-4.1 with custom prompts
- **New**: Semantic Kernel's built-in handoff system with declarative handoff rules

### 3. **Agent Plugins**
- **Original**: Standalone functions and tools
- **New**: Semantic Kernel plugins with `@kernel_function` decorators

### 4. **Authentication**
- **Both**: Use `DefaultAzureCredential` for Azure authentication
- **New**: Uses async credential (`azure.identity.aio.DefaultAzureCredential`)

## Architecture

### Agent Structure
1. **Cora** - Main greeting and general shopping assistant
2. **InteriorDesigner** - Product recommendations, design advice, image analysis
3. **CustomerLoyalty** - Discount calculations and rewards
4. **Inventory** - Stock availability and product details

### Handoff Rules
```
Cora → InteriorDesigner (design/products)
Cora → CustomerLoyalty (discounts)
Cora → Inventory (stock info)

InteriorDesigner → Cora (general questions)
CustomerLoyalty → Cora (after discount info)
Inventory → Cora (after stock check)
```

### Plugins Implemented
- **ProductSearchPlugin**: Search product catalog
- **ImageAnalysisPlugin**: Analyze uploaded images
- **ImageCreationPlugin**: Generate interior design images
- **CartManagementPlugin**: Manage shopping cart
- **CustomerLoyaltyPlugin**: Calculate customer discounts

## File Structure

```
chat_app_sk.py              # New Semantic Kernel application
chat_app.py                 # Original application (kept for reference)
step4_handoff.py           # Reference implementation from workshop
```

## Running the Application

### Start Server
```bash
cd /workspaces/TechWorkshop-L300-AI-Apps-and-agents/src
source venv/bin/activate
python chat_app_sk.py
```

### Access Points
- **Web Interface**: http://localhost:8000
- **Health Check**: http://localhost:8000/health
- **WebSocket**: ws://localhost:8000/ws

## Environment Variables Required

```properties
# Azure AI Foundry (for Semantic Kernel agents)
AZURE_AI_AGENT_ENDPOINT=your_endpoint
AZURE_AI_AGENT_MODEL_DEPLOYMENT_NAME=gpt-4.1
AZURE_AI_AGENT_API_VERSION=2024-12-01-preview

# Azure OpenAI (for LLM calls)
AZURE_OPENAI_ENDPOINT=your_endpoint
AZURE_OPENAI_KEY=your_key
AZURE_OPENAI_API_VERSION=2024-12-01-preview

# Application Insights (optional)
APPLICATIONINSIGHTS_CONNECTION_STRING=your_connection_string

# Other services (search, cosmos, storage)
SEARCH_ENDPOINT=your_search_endpoint
SEARCH_KEY=your_search_key
INDEX_NAME=zava-product-catalog
```

## Key Features

### 1. **Automatic Agent Handoffs**
Semantic Kernel automatically routes conversations between agents based on defined handoff rules.

### 2. **Function Calling**
Agents can call plugin functions for:
- Product search
- Image analysis
- Image creation
- Cart management
- Discount calculation

### 3. **Context Preservation**
- Chat history maintained in deque (maxlen=10)
- Persistent cart across conversation
- Customer ID tracking
- Image URL persistence

### 4. **Error Handling**
- Comprehensive try-catch blocks
- Graceful agent cleanup on session end
- Runtime stop on disconnect

### 5. **Observability**
- Application Insights integration
- OpenTelemetry tracing
- Structured logging
- Performance timing

## Advantages of Semantic Kernel Approach

1. **Declarative Handoffs**: Define agent relationships once, let SK handle routing
2. **Built-in Runtime**: InProcessRuntime manages agent lifecycle
3. **Plugin System**: Reusable, testable functions with decorators
4. **Async Support**: Full async/await support throughout
5. **Extensibility**: Easy to add new agents and capabilities

## Testing

### Test Basic Greeting
```json
{
  "message": "hi",
  "customer_id": "CUST001"
}
```
Expected: Cora greets the user

### Test Product Search
```json
{
  "message": "I need paint for my living room",
  "customer_id": "CUST001"
}
```
Expected: Handoff to InteriorDesigner → product recommendations

### Test Discount Query
```json
{
  "message": "What discount can I get?",
  "customer_id": "CUST001"
}
```
Expected: Handoff to CustomerLoyalty → discount calculation

### Test Stock Check
```json
{
  "message": "Is product XYZ in stock?",
  "customer_id": "CUST001"
}
```
Expected: Handoff to Inventory → stock information

## Troubleshooting

### Issue: Agents not created
- **Solution**: Verify AZURE_AI_AGENT_ENDPOINT is set correctly
- **Check**: Azure AD credentials are valid (`az login`)

### Issue: WebSocket connection fails
- **Solution**: Ensure no other service is using port 8000
- **Check**: Firewall rules allow WebSocket connections

### Issue: Function calls fail
- **Solution**: Verify plugin functions are registered correctly
- **Check**: Function parameter types match schema

## Next Steps

1. **Add More Plugins**: Implement additional business logic as plugins
2. **Enhance Prompts**: Refine agent instructions in prompt files
3. **Add Persistence**: Store conversation history in database
4. **Implement Analytics**: Track agent performance and handoff patterns
5. **Add Tests**: Unit tests for plugins, integration tests for orchestration

## References

- [Semantic Kernel Documentation](https://learn.microsoft.com/en-us/semantic-kernel/)
- [Azure AI Agent Service](https://learn.microsoft.com/en-us/azure/ai-services/agents/)
- [HandoffOrchestration Guide](https://github.com/microsoft/semantic-kernel/blob/main/python/samples/concepts/agents/)
