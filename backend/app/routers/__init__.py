from .config import router as config_router
from .queues import router as queues_router
from .operations import router as operations_router
from .system import router as system_router

__all__ = ["config_router", "queues_router", "operations_router", "system_router"]
