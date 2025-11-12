import logging
import httpx

from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import BasePushNotificationSender, InMemoryPushNotificationConfigStore, InMemoryTaskStore
from a2a.types import AgentCapabilities, AgentCard, AgentSkill

from .agent_executor import SemanticKernelProductManagementExecutor

logger = logging.getLogger(__name__)


class A2AServer:
    """A2A Server wrapper for the Zava Product Helper"""
    
    def __init__(self, httpx_client: httpx.AsyncClient, host: str = "localhost", port: int = 8001):
        self.httpx_client = httpx_client
        self.host = host
        self.port = port
        self._setup_server()
    
    def _setup_server(self):
        """Setup the A2A server with the product helper"""
        # Setup A2A components
        push_config_store = InMemoryPushNotificationConfigStore()
        push_sender = BasePushNotificationSender(self.httpx_client, push_config_store)
        
        request_handler = DefaultRequestHandler(
            agent_executor=SemanticKernelProductManagementExecutor(),
            task_store=InMemoryTaskStore(),
            push_config_store=push_config_store,
            push_sender=push_sender,
        )

        # Create A2A Starlette application
        self.a2a_app = A2AStarletteApplication(
            agent_card=self._get_agent_card(),
            http_handler=request_handler
        )
        
        logger.info(f"A2A server configured for {self.host}:{self.port}")
    
    def _get_agent_card(self) -> AgentCard:
        """Returns the Agent Card for the Zava Product Helper."""
        capabilities = AgentCapabilities(streaming=True)
        
        skill_product_helper = AgentSkill(
            id='product_helper_sk',
            name='Zava Product Helper',
            description='Assists with product information and recommendations for Zava home improvement products',
            tags=[
                'product-search',
                'recommendations',
                'home-improvement',
                'paint',
                'tools',
                'customer-service',
            ],
        )

        agent_card = AgentCard(
            name='Zava Product Helper',
            description='AI assistant specialized in Zava home improvement products and recommendations',
            url=f'http://{self.host}:{self.port}/a2a',
            version='1.0.0',
            defaultSkillId=skill_product_helper.id,
            capabilities=capabilities,
            defaultInputModes=['text'],
            defaultOutputModes=['text'],
            inputContentTypes=['text/plain', 'text'],
            outputContentTypes=['text/plain', 'text'],
            skills=[skill_product_helper],
        )

        return agent_card
    
    def get_starlette_app(self):
        """Get the Starlette app for mounting in FastAPI"""
        return self.a2a_app.build()
