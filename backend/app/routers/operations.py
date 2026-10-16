import asyncio
import json
from typing import List
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from ..models.schemas import (
    OperationRecord,
    OperationRequest,
    OperationStatus,
    RecoveryRequest,
)
from ..services.journal import journal
from ..services.orchestrator import orchestrator

router = APIRouter(prefix="/api/operations", tags=["Operations"])


@router.post("", response_model=OperationRecord)
async def create_operation(request: OperationRequest) -> OperationRecord:
    try:
        record = await orchestrator.start_operation(request)
        return record
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error starting operation: {str(e)}")


@router.get("", response_model=List[OperationRecord])
async def list_operations() -> List[OperationRecord]:
    return journal.list_operations()


@router.get("/recovery-needed", response_model=List[OperationRecord])
async def list_recovery_needed() -> List[OperationRecord]:
    return journal.get_recovery_needed_operations()


@router.get("/{op_id}", response_model=OperationRecord)
async def get_operation(op_id: str) -> OperationRecord:
    record = journal.get_operation(op_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Operation '{op_id}' not found")
    return record


@router.get("/{op_id}/events")
async def stream_operation_events(op_id: str):
    """
    Server-Sent Events (SSE) endpoint providing real-time progress, counts, and logs.
    """
    record = journal.get_operation(op_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Operation '{op_id}' not found")

    async def event_generator():
        last_log_count = 0
        last_updated = ""
        while True:
            current = journal.get_operation(op_id)
            if not current:
                break

            data = current.model_dump()
            yield f"data: {json.dumps(data)}\n\n"

            # Check if finished
            if current.status in (
                OperationStatus.COMPLETED,
                OperationStatus.FAILED,
                OperationStatus.ROLLED_BACK,
                OperationStatus.ABORTED,
            ):
                # Send final event and terminate SSE
                break

            await asyncio.sleep(0.5)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/{op_id}/recover", response_model=OperationRecord)
async def recover_operation(op_id: str, request: RecoveryRequest) -> OperationRecord:
    try:
        record = await orchestrator.recover_operation(op_id, request.action)
        return record
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Recovery failed: {str(e)}")
