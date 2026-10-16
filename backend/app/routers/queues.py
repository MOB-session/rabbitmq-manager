from typing import Any, Dict, List
from fastapi import APIRouter, HTTPException, Query
from ..models.schemas import MessageSample, QueueDetails
from ..services.journal import journal
from ..services.orchestrator import orchestrator

router = APIRouter(prefix="/api/queues", tags=["Queues"])


class EnrichedQueueDetails(QueueDetails):
    is_locked: bool = False
    active_operation_id: str | None = None


@router.get("", response_model=List[EnrichedQueueDetails])
async def list_queues(vhost: str | None = Query(None)) -> List[EnrichedQueueDetails]:
    api_client = orchestrator.get_api_client()
    try:
        queues = await api_client.list_queues(vhost)
        enriched = []
        for q in queues:
            is_locked = journal.is_queue_locked(q.name)
            active_op = journal.get_active_operation_for_queue(q.name)
            enriched.append(
                EnrichedQueueDetails(
                    **q.model_dump(),
                    is_locked=is_locked,
                    active_operation_id=active_op.id if active_op else None,
                )
            )
        return enriched
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch queues: {str(e)}")


@router.get("/{queue_name}", response_model=EnrichedQueueDetails)
async def get_queue(queue_name: str, vhost: str | None = Query(None)) -> EnrichedQueueDetails:
    api_client = orchestrator.get_api_client()
    try:
        q = await api_client.get_queue(queue_name, vhost)
        if not q:
            raise HTTPException(status_code=404, detail=f"Queue '{queue_name}' not found")
        is_locked = journal.is_queue_locked(q.name)
        active_op = journal.get_active_operation_for_queue(q.name)
        return EnrichedQueueDetails(
            **q.model_dump(),
            is_locked=is_locked,
            active_operation_id=active_op.id if active_op else None,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch queue '{queue_name}': {str(e)}")


@router.get("/{queue_name}/sample", response_model=List[MessageSample])
async def sample_messages(
    queue_name: str,
    count: int = Query(5, ge=1, le=50),
    vhost: str | None = Query(None),
) -> List[MessageSample]:
    api_client = orchestrator.get_api_client()
    try:
        samples = await api_client.sample_messages(queue_name, count=count, vhost=vhost)
        return samples
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to sample messages from '{queue_name}': {str(e)}")
