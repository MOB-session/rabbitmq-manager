import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from backend.app.models.schemas import (
    OperationPhase,
    OperationRecord,
    OperationRequest,
    OperationStatus,
    OperationType,
    QueueDetails,
)
from backend.app.services.journal import journal
from backend.app.services.orchestrator import Orchestrator


@pytest.mark.asyncio
async def test_orchestrator_successful_delete():
    orchestrator = Orchestrator()

    mock_queue = QueueDetails(
        name="orders_queue",
        vhost="/",
        type="classic",
        messages=10,
        messages_ready=10,
        messages_unacknowledged=0,
        consumers=0,
        durable=True,
        auto_delete=False,
    )

    with patch.object(orchestrator, "get_api_client") as mock_get_api, patch.object(
        orchestrator, "get_amqp_worker"
    ) as mock_get_amqp:

        mock_api = MagicMock()
        mock_api.get_queue = AsyncMock(return_value=mock_queue)
        mock_api.create_queue = AsyncMock(return_value=True)
        mock_api.delete_queue = AsyncMock(return_value=True)
        mock_api.get_queue_bindings = AsyncMock(return_value=[])
        mock_get_api.return_value = mock_api

        mock_amqp = MagicMock()
        mock_amqp.drain_queue = MagicMock(return_value=10)
        mock_amqp.filter_and_route_queue = MagicMock(
            return_value={
                "inspected": 10,
                "retained": 9,
                "moved": 0,
                "deleted": 1,
                "target_found": True,
            }
        )
        mock_get_amqp.return_value = mock_amqp

        req = OperationRequest(
            source_queue="orders_queue",
            operation_type=OperationType.DELETE,
            target_message_id="order-target-99",
            isolate_producers=False,
            auto_rollback_on_failure=True,
        )

        record = await orchestrator.start_operation(req)
        assert record.id is not None
        assert record.status == OperationStatus.RUNNING

        # Await completion of background task
        # Wait a brief moment for the async task to execute
        import asyncio
        for _ in range(20):
            await asyncio.sleep(0.05)
            updated = journal.get_operation(record.id)
            if updated and updated.status in (OperationStatus.COMPLETED, OperationStatus.FAILED):
                break

        assert updated is not None
        assert updated.status == OperationStatus.COMPLETED
        assert updated.target_found is True
        assert updated.deleted_count == 1
        assert updated.retained_count == 9
        assert updated.restored_count == 10  # from mock drain
