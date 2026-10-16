import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Set
from ..config import DATA_DIR
from ..models.schemas import (
    OperationPhase,
    OperationRecord,
    OperationStatus,
)

logger = logging.getLogger("rmq.journal")
JOURNAL_FILE = DATA_DIR / "operations_journal.json"


class OperationJournal:
    def __init__(self, file_path: Path = JOURNAL_FILE):
        self.file_path = file_path
        self._lock = asyncio.Lock()
        self._locked_queues: Set[str] = set()
        self._operations: Dict[str, OperationRecord] = {}
        self._load()

    def _load(self) -> None:
        if self.file_path.exists():
            try:
                with open(self.file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for op_dict in data:
                        op = OperationRecord(**op_dict)
                        # Check if it was in the middle of running when terminated
                        if op.status in (OperationStatus.RUNNING, OperationStatus.PENDING, OperationStatus.RECOVERING):
                            op.status = OperationStatus.FAILED
                            op.recovery_required = True
                            if not op.error_message:
                                op.error_message = "Process terminated unexpectedly during execution. Recovery required."
                            op.logs.append(f"[{datetime.now(timezone.utc).isoformat()}] Detected interrupted state on server startup.")
                        self._operations[op.id] = op
            except Exception as e:
                logger.error(f"Failed to load operations journal: {e}")

    def _persist(self) -> None:
        try:
            self.file_path.parent.mkdir(parents=True, exist_ok=True)
            data = [op.model_dump() for op in self._operations.values()]
            temp_file = self.file_path.with_suffix(".tmp")
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            temp_file.replace(self.file_path)
        except Exception as e:
            logger.error(f"Failed to persist operations journal: {e}")

    async def acquire_queue_lock(self, queue_names: List[str]) -> bool:
        async with self._lock:
            for q in queue_names:
                if q in self._locked_queues:
                    return False
            for q in queue_names:
                self._locked_queues.add(q)
            return True

    async def release_queue_lock(self, queue_names: List[str]) -> None:
        async with self._lock:
            for q in queue_names:
                self._locked_queues.discard(q)

    def is_queue_locked(self, queue_name: str) -> bool:
        return queue_name in self._locked_queues

    def get_locked_queues(self) -> List[str]:
        return list(self._locked_queues)

    async def save_operation(self, op: OperationRecord) -> None:
        async with self._lock:
            op.updated_at = datetime.now(timezone.utc).isoformat()
            self._operations[op.id] = op
            self._persist()

    async def append_log(self, op_id: str, message: str) -> None:
        async with self._lock:
            op = self._operations.get(op_id)
            if op:
                ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
                op.logs.append(f"[{ts}] {message}")
                op.updated_at = datetime.now(timezone.utc).isoformat()
                self._persist()

    def get_operation(self, op_id: str) -> Optional[OperationRecord]:
        return self._operations.get(op_id)

    def list_operations(self) -> List[OperationRecord]:
        # Return sorted by created_at desc
        return sorted(self._operations.values(), key=lambda x: x.created_at, reverse=True)

    def get_active_operation_for_queue(self, queue_name: str) -> Optional[OperationRecord]:
        for op in self._operations.values():
            if op.request.source_queue == queue_name and op.status in (
                OperationStatus.RUNNING,
                OperationStatus.PENDING,
                OperationStatus.RECOVERING,
            ):
                return op
        return None

    def get_recovery_needed_operations(self) -> List[OperationRecord]:
        return [op for op in self._operations.values() if op.recovery_required]


journal = OperationJournal()
