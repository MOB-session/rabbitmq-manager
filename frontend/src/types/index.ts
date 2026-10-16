export type OperationType = 'move' | 'delete';

export type OperationStatus =
  | 'pending'
  | 'running'
  | 'completed'
  | 'failed'
  | 'aborted'
  | 'recovering'
  | 'recovered'
  | 'rolled_back';

export type OperationPhase =
  | 'idle'
  | 'initializing'
  | 'diverting_traffic'
  | 'draining_to_temp1'
  | 'filtering_to_temp2'
  | 'restoring_source'
  | 'flushing_buffer'
  | 'cleaning_up'
  | 'completed'
  | 'failed'
  | 'rollback_in_progress';

export interface RabbitMQConfig {
  host: string;
  port: number;
  management_port: number;
  vhost: string;
  username: string;
  password?: string;
  use_ssl: boolean;
}

export interface ConnectionTestResult {
  success: boolean;
  message: string;
  rabbitmq_version?: string;
  erlang_version?: string;
  cluster_name?: string;
  amqp_connected: boolean;
}

export interface QueueDetails {
  name: string;
  vhost: string;
  type: string;
  state: string;
  messages: number;
  messages_ready: number;
  messages_unacknowledged: number;
  consumers: number;
  durable: boolean;
  auto_delete: boolean;
  is_locked?: boolean;
  active_operation_id?: string;
}

export interface MessageProperties {
  message_id?: string;
  correlation_id?: string;
  content_type?: string;
  content_encoding?: string;
  delivery_mode?: number;
  priority?: number;
  timestamp?: number;
  type?: string;
  user_id?: string;
  app_id?: string;
  headers?: Record<string, any>;
}

export interface MessageSample {
  payload: string;
  payload_bytes: number;
  payload_encoding: string;
  properties: MessageProperties;
  routing_key: string;
  exchange: string;
  redelivered: boolean;
  message_count: number;
}

export interface OperationRequest {
  source_queue: string;
  operation_type: OperationType;
  target_message_id: string;
  destination_queue?: string;
  isolate_producers: boolean;
  auto_rollback_on_failure: boolean;
}

export interface OperationRecord {
  id: string;
  created_at: string;
  updated_at: string;
  request: OperationRequest;
  status: OperationStatus;
  phase: OperationPhase;
  temp1_queue: string;
  temp2_queue: string;
  buffer_queue?: string;
  initial_count: number;
  transferred_to_temp1: number;
  inspected_count: number;
  target_found: boolean;
  retained_count: number;
  moved_count: number;
  deleted_count: number;
  restored_count: number;
  buffer_count: number;
  error_message?: string;
  logs: string[];
  recovery_required: boolean;
  recovery_info?: Record<string, any>;
}

export type RecoveryAction = 'rollback' | 'resume' | 'discard_temps';

export interface SystemStatus {
  status: string;
  app_name: string;
  app_version: string;
  locked_queues: string[];
  recovery_needed_count: number;
  recovery_needed_ids: string[];
  configured_host: string;
  configured_vhost: string;
}
