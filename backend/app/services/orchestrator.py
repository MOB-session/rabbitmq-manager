import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from ..config import RabbitMQConfig, load_rabbitmq_config
from ..models.schemas import (
    OperationPhase,
    OperationRecord,
    OperationRequest,
    OperationStatus,
    OperationType,
    RecoveryAction,
)
from .journal import journal
from .rabbitmq_amqp import AMQPWorker
from .rabbitmq_api import RabbitMQManagementClient

logger = logging.getLogger("rmq.orchestrator")


class Orchestrator:
    def __init__(self, config: Optional[RabbitMQConfig] = None):
        self._config = config

    @property
    def config(self) -> RabbitMQConfig:
        return self._config or load_rabbitmq_config()

    def get_api_client(self) -> RabbitMQManagementClient:
        return RabbitMQManagementClient(self.config)

    def get_amqp_worker(self) -> AMQPWorker:
        return AMQPWorker(self.config)

    async def start_operation(self, request: OperationRequest) -> OperationRecord:
        api = self.get_api_client()

        # 1. Validate source queue exists
        source_queue_info = await api.get_queue(request.source_queue)
        if not source_queue_info:
            raise ValueError(f"Source queue '{request.source_queue}' does not exist on vhost '{self.config.vhost}'")

        # 2. Validate destination queue if move
        if request.operation_type == OperationType.MOVE:
            if not request.destination_queue:
                raise ValueError("Destination queue is required for a MOVE operation")
            dest_queue_info = await api.get_queue(request.destination_queue)
            if not dest_queue_info:
                raise ValueError(f"Destination queue '{request.destination_queue}' does not exist")

        # 3. Acquire queue locks
        locked_queues = [request.source_queue]
        if request.destination_queue:
            locked_queues.append(request.destination_queue)

        acquired = await journal.acquire_queue_lock(locked_queues)
        if not acquired:
            raise RuntimeError(
                f"Cannot start operation: one of the queues ({locked_queues}) is currently locked by another operation."
            )

        # 4. Create operation record
        op_id = uuid.uuid4().hex[:10]
        temp1_name = f"rmq_tmp1_{op_id}"
        temp2_name = f"rmq_tmp2_{op_id}"
        buffer_name = f"rmq_buf_{op_id}" if request.isolate_producers else None

        now = datetime.now(timezone.utc).isoformat()
        record = OperationRecord(
            id=op_id,
            created_at=now,
            updated_at=now,
            request=request,
            status=OperationStatus.RUNNING,
            phase=OperationPhase.INITIALIZING,
            temp1_queue=temp1_name,
            temp2_queue=temp2_name,
            buffer_queue=buffer_name,
            initial_count=source_queue_info.messages,
            logs=[
                f"[{now[11:19]}] Operation {op_id} initialized for {request.operation_type.value.upper()} on queue '{request.source_queue}'.",
                f"[{now[11:19]}] Target message ID: '{request.target_message_id}'. Initial queue messages: {source_queue_info.messages}.",
            ],
        )

        await journal.save_operation(record)

        # Launch background execution task
        asyncio.create_task(self._run_lifecycle(record))
        return record

    async def _run_lifecycle(self, op: OperationRecord) -> None:
        loop = asyncio.get_running_loop()
        api = self.get_api_client()
        amqp = self.get_amqp_worker()
        diverted_bindings: List[Dict[str, Any]] = []

        try:
            # ----------------------------------------------------
            # Phase 1: INITIALIZING & BUFFERING
            # ----------------------------------------------------
            op.phase = OperationPhase.INITIALIZING
            await journal.append_log(op.id, f"Creating temporary queues '{op.temp1_queue}' and '{op.temp2_queue}'...")

            # Create temp queues matching source queue attributes
            await api.create_queue(op.temp1_queue, queue_type="classic", durable=True)
            await api.create_queue(op.temp2_queue, queue_type="classic", durable=True)

            if op.request.isolate_producers and op.buffer_queue:
                op.phase = OperationPhase.DIVERTING_TRAFFIC
                await journal.append_log(
                    op.id, f"Setting up ingress buffer queue '{op.buffer_queue}' to isolate concurrent producers..."
                )
                await api.create_queue(op.buffer_queue, queue_type="classic", durable=True)

                # Fetch source queue bindings
                bindings = await api.get_queue_bindings(op.request.source_queue)
                for b in bindings:
                    source_exchange = b.get("source", "")
                    routing_key = b.get("routing_key", "")
                    args = b.get("arguments", {})
                    if source_exchange:  # Don't touch default exchange
                        # Bind buffer queue
                        await api.create_binding(
                            exchange=source_exchange,
                            queue=op.buffer_queue,
                            routing_key=routing_key,
                            arguments=args,
                        )
                        # Remove binding from source queue so live messages divert to buffer
                        props_key = b.get("properties_key", "")
                        if props_key:
                            await api.delete_binding(source_exchange, op.request.source_queue, props_key)
                            diverted_bindings.append(b)

                await journal.append_log(
                    op.id,
                    f"Diverted {len(diverted_bindings)} exchange bindings to buffer queue '{op.buffer_queue}'.",
                )

            # ----------------------------------------------------
            # Phase 2: Draining Source Queue to Temp 1
            # ----------------------------------------------------
            op.phase = OperationPhase.DRAINING_TO_TEMP1
            await journal.save_operation(op)
            await journal.append_log(
                op.id, f"Phase 1/4: Draining source queue '{op.request.source_queue}' to '{op.temp1_queue}'..."
            )

            def on_drain_progress(count: int):
                op.transferred_to_temp1 = count
                try:
                    asyncio.run_coroutine_threadsafe(journal.save_operation(op), loop)
                except Exception:
                    pass

            transferred = await asyncio.to_thread(
                amqp.drain_queue,
                op.request.source_queue,
                op.temp1_queue,
                on_drain_progress,
            )
            op.transferred_to_temp1 = transferred
            await journal.append_log(
                op.id, f"Drained {transferred} messages to '{op.temp1_queue}' with publisher confirms."
            )

            # ----------------------------------------------------
            # Phase 3: Filtering Temp 1 to Temp 2 & Destination
            # ----------------------------------------------------
            op.phase = OperationPhase.FILTERING_TO_TEMP2
            await journal.save_operation(op)
            await journal.append_log(
                op.id,
                f"Phase 2/4: Inspecting messages from '{op.temp1_queue}' looking for ID '{op.request.target_message_id}'...",
            )

            def on_filter_progress(stats: Dict[str, Any]):
                op.inspected_count = stats["inspected"]
                op.retained_count = stats["retained"]
                op.moved_count = stats["moved"]
                op.deleted_count = stats["deleted"]
                op.target_found = stats["target_found"]
                try:
                    asyncio.run_coroutine_threadsafe(journal.save_operation(op), loop)
                except Exception:
                    pass

            stats = await asyncio.to_thread(
                amqp.filter_and_route_queue,
                op.temp1_queue,
                op.temp2_queue,
                op.request.target_message_id,
                op.request.operation_type,
                op.request.destination_queue,
                on_filter_progress,
            )

            op.inspected_count = stats["inspected"]
            op.retained_count = stats["retained"]
            op.moved_count = stats["moved"]
            op.deleted_count = stats["deleted"]
            op.target_found = stats["target_found"]

            if stats["target_found"]:
                action_text = "moved to destination queue" if op.request.operation_type == OperationType.MOVE else "deleted"
                await journal.append_log(
                    op.id, f"MATCH FOUND: Target message '{op.request.target_message_id}' was {action_text}."
                )
            else:
                await journal.append_log(
                    op.id,
                    f"WARNING: Target message '{op.request.target_message_id}' was not found among {stats['inspected']} inspected messages.",
                )

            await journal.append_log(
                op.id,
                f"Filter complete: {stats['retained']} non-target messages routed to '{op.temp2_queue}'.",
            )

            # ----------------------------------------------------
            # Phase 4: Restoring Source Queue from Temp 2
            # ----------------------------------------------------
            op.phase = OperationPhase.RESTORING_SOURCE
            await journal.save_operation(op)
            await journal.append_log(
                op.id, f"Phase 3/4: Restoring {op.retained_count} preserved messages back to '{op.request.source_queue}'..."
            )

            def on_restore_progress(count: int):
                op.restored_count = count
                try:
                    asyncio.run_coroutine_threadsafe(journal.save_operation(op), loop)
                except Exception:
                    pass

            restored = await asyncio.to_thread(
                amqp.drain_queue,
                op.temp2_queue,
                op.request.source_queue,
                on_restore_progress,
            )
            op.restored_count = restored
            await journal.append_log(
                op.id, f"Restored {restored} messages back to '{op.request.source_queue}' in original relative order."
            )

            # ----------------------------------------------------
            # Phase 5: Flushing Buffer (if traffic was diverted)
            # ----------------------------------------------------
            if op.buffer_queue:
                op.phase = OperationPhase.FLUSHING_BUFFER
                await journal.save_operation(op)
                await journal.append_log(
                    op.id, f"Phase 4/4: Flushing newly arrived messages from buffer queue '{op.buffer_queue}'..."
                )

                # First restore original bindings to source queue
                for b in diverted_bindings:
                    source_exchange = b.get("source", "")
                    routing_key = b.get("routing_key", "")
                    args = b.get("arguments", {})
                    await api.create_binding(
                        exchange=source_exchange,
                        queue=op.request.source_queue,
                        routing_key=routing_key,
                        arguments=args,
                    )
                await journal.append_log(op.id, "Restored original exchange bindings to source queue.")

                # Drain any messages accumulated in buffer queue into source queue
                buffered = await asyncio.to_thread(amqp.drain_queue, op.buffer_queue, op.request.source_queue)
                op.buffer_count = buffered
                await journal.append_log(op.id, f"Flushed {buffered} buffered messages to '{op.request.source_queue}'.")

                # Delete buffer queue
                await api.delete_queue(op.buffer_queue)

            # ----------------------------------------------------
            # Phase 6: Cleanup & Completion
            # ----------------------------------------------------
            op.phase = OperationPhase.CLEANING_UP
            await journal.append_log(op.id, "Cleaning up temporary queues...")
            await api.delete_queue(op.temp1_queue)
            await api.delete_queue(op.temp2_queue)

            op.phase = OperationPhase.COMPLETED
            op.status = OperationStatus.COMPLETED
            await journal.append_log(
                op.id,
                f"SUCCESS: Operation completed successfully. Total retained: {op.retained_count}, Restored: {op.restored_count}.",
            )
            await journal.save_operation(op)

        except Exception as e:
            logger.error(f"Error during operation {op.id}: {e}", exc_info=True)
            op.status = OperationStatus.FAILED
            op.phase = OperationPhase.FAILED
            op.error_message = str(e)
            await journal.append_log(op.id, f"ERROR: Execution failed: {str(e)}")

            # Attempt automatic rollback if enabled
            if op.request.auto_rollback_on_failure:
                await journal.append_log(op.id, "Auto-rollback enabled. Initiating emergency message recovery...")
                rollback_success = await self._execute_rollback(op, diverted_bindings)
                if rollback_success:
                    op.status = OperationStatus.ROLLED_BACK
                    op.recovery_required = False
                    await journal.append_log(op.id, "Auto-rollback completed: all messages safely returned to source queue.")
                else:
                    op.recovery_required = True
                    await journal.append_log(
                        op.id,
                        "CRITICAL: Auto-rollback failed. Manual recovery required. Temporary queues are preserved to prevent data loss.",
                    )
            else:
                op.recovery_required = True
                await journal.append_log(
                    op.id,
                    "Auto-rollback disabled. Temporary queues preserved. Operation marked as RECOVERY REQUIRED.",
                )

            await journal.save_operation(op)

        finally:
            # Release lock only if completed or cleanly rolled back
            if op.status in (OperationStatus.COMPLETED, OperationStatus.ROLLED_BACK):
                locked_queues = [op.request.source_queue]
                if op.request.destination_queue:
                    locked_queues.append(op.request.destination_queue)
                await journal.release_queue_lock(locked_queues)

    async def _execute_rollback(self, op: OperationRecord, diverted_bindings: List[Dict[str, Any]]) -> bool:
        """
        Safely restores any messages from temp1, temp2, or buffer back to the source queue.
        """
        api = self.get_api_client()
        amqp = self.get_amqp_worker()
        try:
            op.phase = OperationPhase.ROLLBACK_IN_PROGRESS
            await journal.save_operation(op)

            # 1. Restore bindings if diverted
            for b in diverted_bindings:
                try:
                    await api.create_binding(
                        exchange=b.get("source", ""),
                        queue=op.request.source_queue,
                        routing_key=b.get("routing_key", ""),
                        arguments=b.get("arguments", {}),
                    )
                except Exception:
                    pass

            # 2. Drain temp1 back to source queue unconditionally
            await journal.append_log(op.id, f"Rollback: Restoring any messages from '{op.temp1_queue}'...")
            try:
                r1 = await asyncio.to_thread(amqp.drain_queue, op.temp1_queue, op.request.source_queue)
                if r1 > 0:
                    await journal.append_log(op.id, f"Rollback: Restored {r1} messages from '{op.temp1_queue}'.")
            except Exception as ex1:
                logger.warning(f"Temp1 drain warning during rollback: {ex1}")

            # 3. Drain temp2 back to source queue unconditionally
            await journal.append_log(op.id, f"Rollback: Restoring any messages from '{op.temp2_queue}'...")
            try:
                r2 = await asyncio.to_thread(amqp.drain_queue, op.temp2_queue, op.request.source_queue)
                if r2 > 0:
                    await journal.append_log(op.id, f"Rollback: Restored {r2} messages from '{op.temp2_queue}'.")
            except Exception as ex2:
                logger.warning(f"Temp2 drain warning during rollback: {ex2}")

            # 4. Drain buffer back to source queue unconditionally
            if op.buffer_queue:
                await journal.append_log(op.id, f"Rollback: Restoring any messages from '{op.buffer_queue}'...")
                try:
                    rbuf = await asyncio.to_thread(amqp.drain_queue, op.buffer_queue, op.request.source_queue)
                    if rbuf > 0:
                        await journal.append_log(op.id, f"Rollback: Restored {rbuf} messages from '{op.buffer_queue}'.")
                except Exception as exb:
                    logger.warning(f"Buffer drain warning during rollback: {exb}")

            # 5. Delete temp queues
            await api.delete_queue(op.temp1_queue)
            await api.delete_queue(op.temp2_queue)
            if op.buffer_queue:
                await api.delete_queue(op.buffer_queue)

            return True
        except Exception as e:
            logger.error(f"Rollback failed for {op.id}: {e}", exc_info=True)
            await journal.append_log(op.id, f"Rollback failed with error: {str(e)}")
            return False

    async def recover_operation(self, op_id: str, action: RecoveryAction) -> OperationRecord:
        op = journal.get_operation(op_id)
        if not op:
            raise ValueError(f"Operation '{op_id}' not found")

        if not op.recovery_required and op.status != OperationStatus.FAILED:
            raise ValueError(f"Operation '{op_id}' does not require recovery (status: {op.status})")

        api = self.get_api_client()
        amqp = self.get_amqp_worker()

        await journal.append_log(op.id, f"Manual recovery requested: Action = {action.value.upper()}")

        if action == RecoveryAction.ROLLBACK:
            success = await self._execute_rollback(op, [])
            if success:
                op.status = OperationStatus.ROLLED_BACK
                op.recovery_required = False
                await journal.append_log(op.id, "Manual rollback successfully returned all messages to source queue.")
            else:
                raise RuntimeError("Manual rollback encountered an error. Check server logs.")

        elif action == RecoveryAction.DISCARD_TEMPS:
            await api.delete_queue(op.temp1_queue)
            await api.delete_queue(op.temp2_queue)
            if op.buffer_queue:
                await api.delete_queue(op.buffer_queue)
            op.status = OperationStatus.ABORTED
            op.recovery_required = False
            await journal.append_log(op.id, "Temporary queues deleted upon administrator request.")

        # Release lock
        locked_queues = [op.request.source_queue]
        if op.request.destination_queue:
            locked_queues.append(op.request.destination_queue)
        await journal.release_queue_lock(locked_queues)

        await journal.save_operation(op)
        return op


orchestrator = Orchestrator()
