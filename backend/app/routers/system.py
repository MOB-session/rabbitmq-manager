from typing import Any, Dict, List
from fastapi import APIRouter
from ..config import settings
from ..services.journal import journal
from ..services.orchestrator import orchestrator

router = APIRouter(prefix="/api/system", tags=["System"])


@router.get("/status")
async def system_status() -> Dict[str, Any]:
    locked_queues = journal.get_locked_queues()
    recovery_needed = [op.id for op in journal.get_recovery_needed_operations()]
    return {
        "status": "healthy",
        "app_name": settings.app_name,
        "app_version": settings.app_version,
        "locked_queues": locked_queues,
        "recovery_needed_count": len(recovery_needed),
        "recovery_needed_ids": recovery_needed,
        "configured_host": orchestrator.config.host,
        "configured_vhost": orchestrator.config.vhost,
    }
