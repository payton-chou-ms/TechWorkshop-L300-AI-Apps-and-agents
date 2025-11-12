import logging

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events.event_queue import EventQueue
from a2a.types import (
    TaskArtifactUpdateEvent,
    TaskState,
    TaskStatus,
    TaskStatusUpdateEvent,
)
from a2a.utils import (
    new_agent_text_message,
    new_task,
    new_text_artifact,
)
from .product_management_agent import SemanticKernelProductManagementAgent

logger = logging.getLogger(__name__)


class SemanticKernelProductManagementExecutor(AgentExecutor):
    """SemanticKernelProductManagement Executor for A2A Protocol"""

    def __init__(self):
        self.agent = SemanticKernelProductManagementAgent()

    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        """Execute agent request with A2A protocol support
        
        Args:
            context: Request context containing user input and task info
            event_queue: Event queue for publishing task updates
        """
        query = context.get_user_input()
        task = context.current_task
        if not task:
            task = new_task(context.message)
            await event_queue.enqueue_event(task)

        async for partial in self.agent.stream(query, task.contextId):
            require_input = partial['require_user_input']
            is_done = partial['is_task_complete']
            text_content = partial['content']

            if require_input:
                await event_queue.enqueue_event(
                    TaskStatusUpdateEvent(
                        taskId=task.id,
                        status=TaskStatus(
                            state=TaskState.INPUT_REQUIRED,
                        ),
                    )
                )
            elif is_done:
                await event_queue.enqueue_event(
                    TaskArtifactUpdateEvent(
                        taskId=task.id,
                        artifact=new_text_artifact(text_content),
                    )
                )
            else:
                await event_queue.enqueue_event(
                    new_agent_text_message(
                        task_id=task.id, text_content=text_content
                    )
                )

    async def cancel(
        self, context: RequestContext, event_queue: EventQueue
    ) -> None:
        """Cancel the current task execution"""
        logger.warning("Task cancellation requested but not implemented")
        raise Exception('cancel not supported')
