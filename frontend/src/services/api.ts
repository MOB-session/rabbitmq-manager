import {
  ConnectionTestResult,
  MessageSample,
  OperationRecord,
  OperationRequest,
  QueueDetails,
  RabbitMQConfig,
  RecoveryAction,
  SystemStatus,
} from '../types';

const BASE_URL = '/api';

export const api = {
  async getConfig(): Promise<RabbitMQConfig> {
    const res = await fetch(`${BASE_URL}/config`);
    if (!res.ok) throw new Error(`Failed to load config: ${res.statusText}`);
    return res.json();
  },

  async updateConfig(config: RabbitMQConfig): Promise<RabbitMQConfig> {
    const res = await fetch(`${BASE_URL}/config`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(config),
    });
    if (!res.ok) throw new Error(`Failed to update config: ${res.statusText}`);
    return res.json();
  },

  async testConnection(config?: RabbitMQConfig): Promise<ConnectionTestResult> {
    const res = await fetch(`${BASE_URL}/config/test`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: config ? JSON.stringify(config) : undefined,
    });
    if (!res.ok) throw new Error(`Connection test failed: ${res.statusText}`);
    return res.json();
  },

  async listQueues(vhost?: string): Promise<QueueDetails[]> {
    const url = vhost ? `${BASE_URL}/queues?vhost=${encodeURIComponent(vhost)}` : `${BASE_URL}/queues`;
    const res = await fetch(url);
    if (!res.ok) throw new Error(`Failed to fetch queues: ${res.statusText}`);
    return res.json();
  },

  async sampleMessages(queueName: string, count = 5, vhost?: string): Promise<MessageSample[]> {
    const params = new URLSearchParams({ count: count.toString() });
    if (vhost) params.append('vhost', vhost);
    const res = await fetch(`${BASE_URL}/queues/${encodeURIComponent(queueName)}/sample?${params.toString()}`);
    if (!res.ok) throw new Error(`Failed to sample messages: ${res.statusText}`);
    return res.json();
  },

  async startOperation(request: OperationRequest): Promise<OperationRecord> {
    const res = await fetch(`${BASE_URL}/operations`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request),
    });
    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.detail || `Operation request failed with status ${res.status}`);
    }
    return res.json();
  },

  async listOperations(): Promise<OperationRecord[]> {
    const res = await fetch(`${BASE_URL}/operations`);
    if (!res.ok) throw new Error(`Failed to fetch operations: ${res.statusText}`);
    return res.json();
  },

  async getOperation(opId: string): Promise<OperationRecord> {
    const res = await fetch(`${BASE_URL}/operations/${opId}`);
    if (!res.ok) throw new Error(`Failed to fetch operation ${opId}: ${res.statusText}`);
    return res.json();
  },

  async recoverOperation(opId: string, action: RecoveryAction): Promise<OperationRecord> {
    const res = await fetch(`${BASE_URL}/operations/${opId}/recover`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Recovery failed: ${res.statusText}`);
    }
    return res.json();
  },

  async getSystemStatus(): Promise<SystemStatus> {
    const res = await fetch(`${BASE_URL}/system/status`);
    if (!res.ok) throw new Error(`Failed to fetch system status: ${res.statusText}`);
    return res.json();
  },
};
