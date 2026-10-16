from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class OperationType(str, Enum):
    MOVE = "move"
    DELETE = "delete"


class OperationStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    ABORTED = "aborted"
    RECOVERING = "recovering"
    RECOVERED = "recovered"
    ROLLED_BACK = "rolled_back"


class OperationPhase(str, Enum):
    IDLE = "idle"
    INITIALIZING = "initializing"
    DIVERTING_TRAFFIC = "diverting_traffic"
    DRAINING_TO_TEMP1 = "draining_to_temp1"
    FILTERING_TO_TEMP2 = "filtering_to_temp2"
    RESTORING_SOURCE = "restoring_source"
    FLUSHING_BUFFER = "flushing_buffer"
    CLEANING_UP = "cleaning_up"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLBACK_IN_PROGRESS = "rollback_in_progress"


class QueueDetails(BaseModel):
    name: str
    vhost: str
    type: str = "classic"  # classic, quorum, stream
    state: str = "running"
    messages: int = 0
    messages_ready: int = 0
    messages_unacknowledged: int = 0
    consumers: int = 0
    durable: bool = True
    auto_delete: bool = False
    policy: Optional[str] = None
    node: Optional[str] = None


class MessageProperties(BaseModel):
    message_id: Optional[str] = None
    correlation_id: Optional[str] = None
    content_type: Optional[str] = None
    content_encoding: Optional[str] = None
    delivery_mode: Optional[int] = None
    priority: Optional[int] = None
    timestamp: Optional[int] = None
    type: Optional[str] = None
    user_id: Optional[str] = None
    app_id: Optional[str] = None
    headers: Optional[Dict[str, Any]] = None


class MessageSample(BaseModel):
    payload: str
    payload_bytes: int
    payload_encoding: str = "string"
    properties: MessageProperties
    routing_key: str = ""
    exchange: str = ""
    redelivered: bool = False
    message_count: int = 0


class ConnectionTestResult(BaseModel):
    success: bool
    message: str
    rabbitmq_version: Optional[str] = None
    erlang_version: Optional[str] = None
    cluster_name: Optional[str] = None
    amqp_connected: bool = False


class OperationRequest(BaseModel):
    source_queue: str = Field(..., description="Source queue containing target message")
    operation_type: OperationType = Field(..., description="Move or Delete")
    target_message_id: str = Field(..., description="Message ID or custom identifier")
    destination_queue: Optional[str] = Field(
        None, description="Destination queue (required for move operation)"
    )
    isolate_producers: bool = Field(
        default=True,
        description="Divert incoming messages to buffer queue during execution to maintain strict FIFO order",
    )
    auto_rollback_on_failure: bool = Field(
        default=True,
        description="Automatically restore messages to source queue if an error occurs",
    )


class OperationRecord(BaseModel):
    id: str
    created_at: str
    updated_at: str
    request: OperationRequest
    status: OperationStatus
    phase: OperationPhase
    temp1_queue: str
    temp2_queue: str
    buffer_queue: Optional[str] = None
    initial_count: int = 0
    transferred_to_temp1: int = 0
    inspected_count: int = 0
    target_found: bool = False
    retained_count: int = 0
    moved_count: int = 0
    deleted_count: int = 0
    restored_count: int = 0
    buffer_count: int = 0
    error_message: Optional[str] = None
    logs: List[str] = Field(default_factory=list)
    recovery_required: bool = False
    recovery_info: Optional[Dict[str, Any]] = None


class RecoveryAction(str, Enum):
    ROLLBACK = "rollback"  # Restores all messages from Temp1 / Temp2 / Buffer back to Source
    RESUME = "resume"  # Continues the remaining phases of the operation
    DISCARD_TEMPS = "discard_temps"  # Cleans up temporary queues after manual inspection


class RecoveryRequest(BaseModel):
    action: RecoveryAction
