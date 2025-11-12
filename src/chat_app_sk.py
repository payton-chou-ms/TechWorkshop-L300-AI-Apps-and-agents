"""
FastAPI Chat Application with Semantic Kernel Handoff Orchestration
Integrates Zava shopping assistant agents using Semantic Kernel's HandoffOrchestration
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
import os
from dotenv import load_dotenv
from azure.identity.aio import DefaultAzureCredential
from collections import deque
from typing import Deque, Tuple, Optional, Dict
import orjson
import asyncio
import datetime
import time
import logging
from opentelemetry import trace
from azure.monitor.opentelemetry import configure_azure_monitor

# Semantic Kernel imports
from semantic_kernel.agents import (
    Agent,
    AzureAIAgent,
    AzureAIAgentSettings,
    HandoffOrchestration,
    OrchestrationHandoffs,
)
from semantic_kernel.agents.runtime import InProcessRuntime
from semantic_kernel.contents import (
    AuthorRole,
    ChatMessageContent,
    FunctionCallContent,
    FunctionResultContent,
)
from semantic_kernel.functions import kernel_function

# Import utilities
from utils.env_utils import load_env_vars, validate_env_vars
from utils.response_utils import parse_agent_response
from app.tools.aiSearchTools import product_recommendations
from app.tools.understandImage import get_image_description
from app.tools.imageCreationTool import create_image

load_dotenv(override=True)

# Configure logging
logging.basicConfig(
    level=logging.INFO if os.getenv('DEBUG') else logging.WARNING,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configure Application Insights
application_insights_connection_string = os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING")
if application_insights_connection_string:
    configure_azure_monitor(connection_string=application_insights_connection_string)

scenario = os.path.basename(__file__)
tracer = trace.get_tracer(__name__)

# Load environment variables
env_vars = load_env_vars()
validated_env_vars = validate_env_vars(env_vars)

app = FastAPI()

# Optimized JSON serialization
def fast_json_dumps(obj, **kwargs):
    """Use orjson for faster JSON serialization."""
    return orjson.dumps(obj, **kwargs).decode('utf-8')


# ==================== Semantic Kernel Agent Plugins ====================

class ProductSearchPlugin:
    """Plugin for searching products in the catalog."""
    
    @kernel_function(description="Search for products based on user query")
    def search_products(self, query: str) -> str:
        """Search for products in the catalog."""
        try:
            products = product_recommendations(query)
            if products:
                return fast_json_dumps(products)
            return "[]"
        except Exception as e:
            logger.error(f"Error searching products: {e}")
            return "[]"


class ImageAnalysisPlugin:
    """Plugin for analyzing images."""
    
    def __init__(self):
        self.image_cache = {}
    
    @kernel_function(description="Analyze an image and return description")
    def analyze_image(self, image_url: str) -> str:
        """Analyze an image and return its description."""
        try:
            if image_url in self.image_cache:
                return self.image_cache[image_url]
            
            description = get_image_description(image_url)
            self.image_cache[image_url] = description
            return description
        except Exception as e:
            logger.error(f"Error analyzing image: {e}")
            return ""


class ImageCreationPlugin:
    """Plugin for creating images."""
    
    @kernel_function(description="Create an image based on description and reference image")
    def create_room_image(self, description: str, reference_image_url: str = "") -> str:
        """Create an image for interior design."""
        try:
            image_url = create_image(text=description, image_url=reference_image_url)
            return image_url
        except Exception as e:
            logger.error(f"Error creating image: {e}")
            return ""


class CartManagementPlugin:
    """Plugin for managing shopping cart."""
    
    def __init__(self):
        self.cart = []
    
    @kernel_function(description="Add product to cart")
    def add_to_cart(self, product_id: str, product_name: str, quantity: int = 1) -> str:
        """Add a product to the shopping cart."""
        item = {
            "product_id": product_id,
            "product_name": product_name,
            "quantity": quantity
        }
        self.cart.append(item)
        return f"Added {product_name} to cart. Cart now has {len(self.cart)} items."
    
    @kernel_function(description="Get current cart contents")
    def get_cart(self) -> str:
        """Get the current cart contents."""
        return fast_json_dumps(self.cart)
    
    @kernel_function(description="Clear the shopping cart")
    def clear_cart(self) -> str:
        """Clear all items from the cart."""
        self.cart.clear()
        return "Cart cleared successfully."


class CustomerLoyaltyPlugin:
    """Plugin for customer loyalty and discounts."""
    
    @kernel_function(description="Calculate customer discount based on customer ID")
    def calculate_discount(self, customer_id: str) -> str:
        """Calculate discount percentage for a customer."""
        # Simplified logic - in production, query from database
        if customer_id == "CUST001":
            return "15%"
        return "10%"


# ==================== Agent Setup ====================

async def setup_agents(client) -> tuple[list[Agent], OrchestrationHandoffs, dict]:
    """Setup Zava shopping assistant agents with handoff orchestration."""
    
    # Load prompts
    prompts_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'prompts')
    
    with open(os.path.join(prompts_dir, 'ShopperAgentPrompt.txt'), 'r') as f:
        shopper_prompt = f.read()
    
    with open(os.path.join(prompts_dir, 'InteriorDesignAgentPrompt.txt'), 'r') as f:
        interior_designer_prompt = f.read()
    
    with open(os.path.join(prompts_dir, 'CustomerLoyaltyAgentPrompt.txt'), 'r') as f:
        loyalty_prompt = f.read()
    
    with open(os.path.join(prompts_dir, 'InventoryAgentPrompt.txt'), 'r') as f:
        inventory_prompt = f.read()
    
    # Create shared plugins
    product_search_plugin = ProductSearchPlugin()
    image_analysis_plugin = ImageAnalysisPlugin()
    image_creation_plugin = ImageCreationPlugin()
    cart_plugin = CartManagementPlugin()
    loyalty_plugin = CustomerLoyaltyPlugin()
    
    # 1. Cora - Main shopper agent (greeting and general assistance)
    cora_definition = await client.agents.create_agent(
        model=AzureAIAgentSettings().model_deployment_name,
        name="Cora",
        description="Main greeting and general shopping assistant for Zava",
        instructions=shopper_prompt,
    )
    cora_agent = AzureAIAgent(
        client=client,
        definition=cora_definition,
    )
    
    # 2. Interior Designer Agent (product recommendations and design advice)
    interior_designer_definition = await client.agents.create_agent(
        model=AzureAIAgentSettings().model_deployment_name,
        name="InteriorDesigner",
        description="Interior design expert providing product recommendations",
        instructions=interior_designer_prompt,
        tools=[
            {
                "type": "function",
                "function": {
                    "name": "ProductSearchPlugin-search_products",
                    "description": "Search for products based on user query",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Search query for products"}
                        },
                        "required": ["query"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "ImageAnalysisPlugin-analyze_image",
                    "description": "Analyze an image and return description",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "image_url": {"type": "string", "description": "URL of the image to analyze"}
                        },
                        "required": ["image_url"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "ImageCreationPlugin-create_room_image",
                    "description": "Create an image for interior design",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "description": {"type": "string", "description": "Description of the desired image"},
                            "reference_image_url": {"type": "string", "description": "Optional reference image URL"}
                        },
                        "required": ["description"],
                    },
                },
            },
        ],
    )
    interior_designer_agent = AzureAIAgent(
        client=client,
        definition=interior_designer_definition,
        plugins=[product_search_plugin, image_analysis_plugin, image_creation_plugin],
    )
    
    # 3. Customer Loyalty Agent (discounts and promotions)
    loyalty_definition = await client.agents.create_agent(
        model=AzureAIAgentSettings().model_deployment_name,
        name="CustomerLoyalty",
        description="Customer loyalty and discount specialist",
        instructions=loyalty_prompt,
        tools=[
            {
                "type": "function",
                "function": {
                    "name": "CustomerLoyaltyPlugin-calculate_discount",
                    "description": "Calculate customer discount based on customer ID",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "customer_id": {"type": "string", "description": "Customer ID"}
                        },
                        "required": ["customer_id"],
                    },
                },
            }
        ],
    )
    loyalty_agent = AzureAIAgent(
        client=client,
        definition=loyalty_definition,
        plugins=[loyalty_plugin],
    )
    
    # 4. Inventory Agent (stock checking and availability)
    inventory_definition = await client.agents.create_agent(
        model=AzureAIAgentSettings().model_deployment_name,
        name="Inventory",
        description="Inventory and stock availability specialist",
        instructions=inventory_prompt,
        tools=[
            {
                "type": "function",
                "function": {
                    "name": "ProductSearchPlugin-search_products",
                    "description": "Search for products based on user query",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Search query for products"}
                        },
                        "required": ["query"],
                    },
                },
            }
        ],
    )
    inventory_agent = AzureAIAgent(
        client=client,
        definition=inventory_definition,
        plugins=[product_search_plugin],
    )
    
    # Define handoff relationships
    handoffs = (
        OrchestrationHandoffs()
        .add_many(
            source_agent=cora_agent.name,
            target_agents={
                interior_designer_agent.name: "Transfer to interior designer for product recommendations, design advice, or image analysis",
                loyalty_agent.name: "Transfer to loyalty agent for discount information or customer rewards",
                inventory_agent.name: "Transfer to inventory agent for stock availability or product details",
            },
        )
        .add(
            source_agent=interior_designer_agent.name,
            target_agent=cora_agent.name,
            description="Transfer back to Cora for general questions or if user wants to change topic",
        )
        .add(
            source_agent=loyalty_agent.name,
            target_agent=cora_agent.name,
            description="Transfer back to Cora after providing discount information",
        )
        .add(
            source_agent=inventory_agent.name,
            target_agent=cora_agent.name,
            description="Transfer back to Cora after checking inventory",
        )
    )
    
    agents = [cora_agent, interior_designer_agent, loyalty_agent, inventory_agent]
    
    # Store plugins for access
    plugins = {
        'cart': cart_plugin,
        'image_analysis': image_analysis_plugin,
    }
    
    return agents, handoffs, plugins


# ==================== FastAPI Routes ====================

@app.get("/")
async def get():
    """Serve the chat HTML interface."""
    chat_html_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'chat.html')
    with open(chat_html_path, "r", encoding="utf-8") as f:
        return HTMLResponse(f.read())


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.datetime.now().isoformat(),
        "framework": "semantic_kernel",
        "environment_vars_configured": {
            "azure_ai_agent_endpoint": bool(os.environ.get("AZURE_AI_AGENT_ENDPOINT")),
            "azure_openai_endpoint": bool(validated_env_vars.get('AZURE_OPENAI_ENDPOINT')),
        }
    }


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time chat with Semantic Kernel handoff orchestration."""
    session_start_time = time.time()
    logger.info("WebSocket Session Started with Semantic Kernel")
    
    await websocket.accept()
    
    # Session variables
    chat_history: Deque[Tuple[str, str]] = deque(maxlen=10)
    persistent_cart = []
    persistent_image_url = ""
    customer_id = "CUST001"
    
    # Message collection for orchestration
    collected_messages = []
    
    # Response callback for agent messages
    def agent_response_callback(message: ChatMessageContent) -> None:
        """Collect messages from agents during orchestration."""
        collected_messages.append({
            "agent": message.name,
            "content": message.content,
            "role": str(message.role)
        })
        
        # Log function calls for debugging
        for item in message.items:
            if isinstance(item, FunctionCallContent):
                logger.debug(f"Agent {message.name} calling '{item.name}' with args '{item.arguments}'")
            if isinstance(item, FunctionResultContent):
                logger.debug(f"Function '{item.name}' returned: '{item.result}'")
    
    # Initialize Semantic Kernel runtime and agents
    runtime = None
    agents = None
    orchestration = None
    plugins = None
    
    try:
        async with DefaultAzureCredential() as creds:
            async with AzureAIAgent.create_client(credential=creds) as client:
                # Setup agents and orchestration
                agents, handoffs, plugins = await setup_agents(client)
                
                # Create handoff orchestration
                orchestration = HandoffOrchestration(
                    members=agents,
                    handoffs=handoffs,
                    agent_response_callback=agent_response_callback,
                )
                
                # Create and start runtime
                runtime = InProcessRuntime()
                runtime.start()
                
                logger.info("Semantic Kernel orchestration initialized successfully")
                
                # Main message loop
                try:
                    while True:
                        message_start_time = time.time()
                        
                        try:
                            # Receive message from client
                            data = await websocket.receive_text()
                            parsed = orjson.loads(data)
                            user_message = parsed.get("message", "")
                            has_image = parsed.get("has_image", False)
                            image_url = parsed.get("image_url", "")
                            has_video = parsed.get("has_video", False)
                            video_url = parsed.get("video_url", "")
                            cart = parsed.get("cart", [])
                            
                            # Update persistent image URL
                            if image_url:
                                persistent_image_url = image_url
                            
                            # Update cart
                            if cart:
                                persistent_cart = cart
                            
                            logger.info(f"Received message: {user_message[:50]}...")
                            
                        except WebSocketDisconnect:
                            logger.info("WebSocket connection terminated")
                            break
                        except Exception as e:
                            logger.error(f"Error parsing message: {e}")
                            continue
                        
                        # Build task with context
                        task = user_message
                        if has_image and image_url:
                            task += f"\n[User provided image: {image_url}]"
                        if has_video and video_url:
                            task += f"\n[User provided video: {video_url}]"
                        if customer_id:
                            task += f"\n[Customer ID: {customer_id}]"
                        if persistent_cart:
                            task += f"\n[Current cart: {len(persistent_cart)} items]"
                        
                        # Clear collected messages
                        collected_messages.clear()
                        
                        try:
                            # Invoke orchestration with the task
                            logger.debug(f"Invoking orchestration with task: {task[:100]}...")
                            orchestration_result = await orchestration.invoke(
                                task=task,
                                runtime=runtime,
                            )
                            
                            # Get the result
                            final_result = await orchestration_result.get()
                            
                            # Extract the final response
                            response_content = ""
                            responding_agent = "Cora"
                            
                            if collected_messages:
                                # Get the last user-facing message
                                for msg in reversed(collected_messages):
                                    if msg.get("content") and msg.get("role") == "AuthorRole.ASSISTANT":
                                        response_content = msg["content"]
                                        responding_agent = msg["agent"]
                                        break
                            
                            if not response_content and final_result:
                                response_content = str(final_result)
                            
                            if not response_content:
                                response_content = "I'm here to help! How can I assist you today?"
                            
                            # Format response
                            response = {
                                "answer": response_content,
                                "agent": responding_agent.lower(),
                                "cart": persistent_cart,
                                "products": "",
                                "discount_percentage": "",
                                "image_url": "",
                                "additional_data": ""
                            }
                            
                            # Send response
                            await websocket.send_text(fast_json_dumps(response))
                            
                            # Update chat history
                            chat_history.append(("user", user_message))
                            chat_history.append(("bot", response_content))
                            
                            elapsed = time.time() - message_start_time
                            logger.info(f"Message processed in {elapsed:.3f}s by {responding_agent}")
                            
                        except Exception as e:
                            logger.error(f"Error during orchestration: {e}", exc_info=True)
                            error_response = {
                                "answer": "I apologize, but I encountered an error processing your request. Please try again.",
                                "error": str(e),
                                "agent": "system",
                                "cart": persistent_cart
                            }
                            await websocket.send_text(fast_json_dumps(error_response))
                
                except WebSocketDisconnect:
                    logger.info("Client disconnected")
                except Exception as e:
                    logger.error(f"WebSocket error: {e}", exc_info=True)
                finally:
                    # Cleanup runtime
                    if runtime:
                        await runtime.stop_when_idle()
                        logger.info("Runtime stopped")
                    
                    # Cleanup agents
                    if agents:
                        for agent in agents:
                            try:
                                await client.agents.delete_agent(agent.id)
                                logger.debug(f"Deleted agent: {agent.name}")
                            except Exception as e:
                                logger.error(f"Error deleting agent {agent.name}: {e}")
    
    except Exception as e:
        logger.error(f"Session initialization error: {e}", exc_info=True)
        try:
            error_response = {
                "answer": "Failed to initialize the chat system. Please refresh and try again.",
                "error": str(e),
                "agent": "system",
                "cart": []
            }
            await websocket.send_text(fast_json_dumps(error_response))
        except:
            pass
    
    finally:
        session_duration = time.time() - session_start_time
        logger.info(f"WebSocket Session Ended - Duration: {session_duration:.3f}s")


if __name__ == "__main__":
    import uvicorn
    
    now = datetime.datetime.now()
    day = now.day
    suffix = 'th' if 11 <= day <= 13 else {1: 'st', 2: 'nd', 3: 'rd'}.get(day % 10, 'th')
    formatted_date = now.strftime(f"%d{suffix} %B %I.%M%p")
    
    print(f"🚀 Starting Zava Chat App with Semantic Kernel - {formatted_date}")
    print(f"📍 Endpoint: http://0.0.0.0:8000")
    print(f"🔧 Framework: Semantic Kernel HandoffOrchestration")
    
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("chat_app_sk:app", host="0.0.0.0", port=port, reload=False)
