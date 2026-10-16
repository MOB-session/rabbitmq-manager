import pytest
from pathlib import Path
from backend.app.models.schemas import (
    OperationPhase,
    OperationRecord,
    OperationRequest,
    OperationStatus,
    OperationType,
)
from backend.app.services.journal import OperationJournal


@pytest.mark.asyncio
async def test_queue_locking(tmp_path: Path):
    test_journal = OperationJournal(file_path=tmp_path / "journal_test.json")

    # Lock source queue
    acquired = await test_journal.acquire_queue_lock(["queue.orders", "queue.deadletter"])
    assert acquired is True
    assert test_journal.is_queue_locked("queue.orders") is True
    assert test_journal.is_queue_locked("queue.deadletter") is True
    assert test_journal.is_queue_locked("queue.other") is False

    # Attempting to lock the same queue should fail
    conflicting = await test_journal.acquire_queue_lock(["queue.orders"])
    assert conflicting is False

    # Release lock
    await test_journal.release_queue_lock(["queue.orders", "queue.deadletter"])
    assert test_journal.is_queue_locked("queue.orders") is False

    # Re-acquire should now succeed
    reacquired = await test_journal.acquire_queue_lock(["queue.orders"])
    assert reacquired is True


@pytest.mark.asyncio
async def test_operation_persistence_and_recovery(tmp_path: Path):
    journal_file = tmp_path / "journal_test.json"
    journal1 = OperationJournal(file_path=journal_file)

    req = OperationRequest(
        source_queue="test_q",
        operation_type=OperationType.DELETE,
        target_message_id="msg-12345",
        isolate_producers=True,
    )
    op = OperationRecord(
        id="op_abc123",
        created_at="2026-10-16T12:00:00Z",
        updated_at="2026-10-16T12:00:00Z",
        request=req,
        status=OperationStatus.RUNNING,  # in progress
        phase=OperationPhase.DRAINING_TO_TEMP1,
        temp1_queue="rmq_tmp1_abc123",
        temp2_queue="rmq_tmp2_abc123",
        buffer_queue="rmq_buf_abc123",
        initial_count=50,
        transferred_to_temp1=20,
    )
    await journal1.save_operation(op)
    await journal1.append_log("op_abc123", "Step completed")

    # Simulate crash and restart: instantiate new journal loading from disk
    journal2 = OperationJournal(file_path=journal_file)
    recovered_op = journal2.get_operation("op_abc123")
    assert recovered_op is not None
    # Because it was in RUNNING state when crashed, it must now be marked as FAILED with recovery_required=True
    assert recovered_op.status == OperationStatus.FAILED
    assert recovered_op.recovery_required is True
    assert len(recovered_op.logs) >= 2
    assert len(journal2.get_recovery_needed_operations()) == 1
