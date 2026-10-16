import React, { useEffect, useState, useCallback } from 'react';
import { Navbar } from './components/Navbar';
import { ConnectionModal } from './components/ConnectionModal';
import { RecoveryAlert } from './components/RecoveryAlert';
import { MessageSampleModal } from './components/MessageSampleModal';
import { OperationForm } from './components/OperationForm';
import { ConfirmationModal } from './components/ConfirmationModal';
import { ExecutionMonitor } from './components/ExecutionMonitor';
import { HistoryTable } from './components/HistoryTable';
import {
  MessageSample,
  OperationRecord,
  OperationRequest,
  QueueDetails,
  RabbitMQConfig,
  SystemStatus,
} from './types';
import { api } from './services/api';
import { Layers, Info, ShieldCheck, Zap } from 'lucide-react';

export const App: React.FC = () => {
  const [config, setConfig] = useState<RabbitMQConfig | null>(null);
  const [systemStatus, setSystemStatus] = useState<SystemStatus | null>(null);
  const [queues, setQueues] = useState<QueueDetails[]>([]);
  const [recoveryOperations, setRecoveryOperations] = useState<OperationRecord[]>([]);
  const [operationsHistory, setOperationsHistory] = useState<OperationRecord[]>([]);
  const [activeOperation, setActiveOperation] = useState<OperationRecord | null>(null);

  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);

  // Message Sampling Modal
  const [sampleQueueName, setSampleQueueName] = useState<string | null>(null);
  const [samples, setSamples] = useState<MessageSample[]>([]);
  const [isSampling, setIsSampling] = useState(false);

  // Confirmation Modal
  const [pendingRequest, setPendingRequest] = useState<OperationRequest | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Initial Data Load
  const loadInitialData = useCallback(async () => {
    setIsRefreshing(true);
    try {
      const [cfg, status, qList, ops] = await Promise.allSettled([
        api.getConfig(),
        api.getSystemStatus(),
        api.listQueues(),
        api.listOperations(),
      ]);

      if (cfg.status === 'fulfilled') setConfig(cfg.value);
      if (status.status === 'fulfilled') setSystemStatus(status.value);
      if (qList.status === 'fulfilled') setQueues(qList.value);
      if (ops.status === 'fulfilled') {
        setOperationsHistory(ops.value);
        setRecoveryOperations(ops.value.filter((op) => op.recovery_required));
      }
    } finally {
      setIsRefreshing(false);
    }
  }, []);

  useEffect(() => {
    loadInitialData();
  }, [loadInitialData]);

  // Periodic polling for status and queue counts
  useEffect(() => {
    const timer = setInterval(() => {
      api.listQueues().then(setQueues).catch(() => {});
      api.getSystemStatus().then(setSystemStatus).catch(() => {});
      api.listOperations().then((ops) => {
        setOperationsHistory(ops);
        setRecoveryOperations(ops.filter((op) => op.recovery_required));
      }).catch(() => {});
    }, 5000);
    return () => clearInterval(timer);
  }, []);

  const handleInspectQueue = async (queueName: string) => {
    setSampleQueueName(queueName);
    setIsSampling(true);
    setSamples([]);
    try {
      const result = await api.sampleMessages(queueName, 8);
      setSamples(result);
    } catch (err) {
      console.error('Sampling failed:', err);
    } finally {
      setIsSampling(false);
    }
  };

  const handleStartOperation = (request: OperationRequest) => {
    setPendingRequest(request);
  };

  const handleConfirmOperation = async () => {
    if (!pendingRequest) return;
    setIsSubmitting(true);
    try {
      const created = await api.startOperation(pendingRequest);
      setActiveOperation(created);
      setPendingRequest(null);
      // Reload queues and operations
      loadInitialData();
    } catch (err: any) {
      alert(`Failed to start operation: ${err.message}`);
    } finally {
      setIsSubmitting(false);
    }
  };

  const sourceQueueDetails = pendingRequest
    ? queues.find((q) => q.name === pendingRequest.source_queue)
    : undefined;

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans">
      <Navbar
        config={config}
        systemStatus={systemStatus}
        onOpenSettings={() => setIsSettingsOpen(true)}
        onRefresh={loadInitialData}
        isRefreshing={isRefreshing}
      />

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
        {/* Recovery Required Alert Banner */}
        <RecoveryAlert
          recoveryOperations={recoveryOperations}
          onRecoveryComplete={loadInitialData}
        />

        {/* Active Execution Monitor if in progress or selected */}
        {activeOperation && (
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-bold uppercase tracking-wider text-orange-400 flex items-center gap-2">
                <Zap className="w-4 h-4" /> Live Operation Monitor
              </h2>
            </div>
            <ExecutionMonitor
              operation={activeOperation}
              onUpdate={(updated) => {
                setActiveOperation(updated);
                setOperationsHistory((prev) =>
                  prev.map((o) => (o.id === updated.id ? updated : o))
                );
              }}
              onClose={() => setActiveOperation(null)}
            />
          </div>
        )}

        {/* Main Work Area: Operation Form + Architecture Notice */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 items-start">
          <div className="lg:col-span-2">
            <OperationForm
              queues={queues}
              onSubmit={handleStartOperation}
              onInspectQueue={handleInspectQueue}
              isInspectLoading={isSampling}
            />
          </div>

          {/* Architecture & Guarantees Panel */}
          <div className="space-y-4">
            <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-5 text-xs space-y-3">
              <div className="flex items-center gap-2 text-slate-200 font-semibold text-sm">
                <ShieldCheck className="w-4 h-4 text-emerald-400" />
                <span>Zero Data-Loss Guarantees</span>
              </div>
              <p className="text-slate-400 leading-relaxed">
                RabbitMQ 4.1.0 does not support in-place random deletion by ID. To preserve message ordering, this
                orchestrator runs an automated 4-phase shuffle:
              </p>

              <ol className="list-decimal list-inside space-y-1.5 text-slate-300 font-mono text-[11px]">
                <li>
                  <strong className="text-orange-400">Temp 1:</strong> Drain source queue.
                </li>
                <li>
                  <strong className="text-orange-400">Filter:</strong> Inspect IDs; route target to destination or purge; non-targets to Temp 2.
                </li>
                <li>
                  <strong className="text-orange-400">Restore:</strong> Return preserved messages to source in original order.
                </li>
                <li>
                  <strong className="text-orange-400">Buffer Flush:</strong> Append live messages received during execution.
                </li>
              </ol>

              <div className="pt-2 border-t border-slate-800 text-slate-400 text-[11px]">
                <strong>Reliability:</strong> Every publish is acknowledged via Publisher Confirms before the source
                message is removed.
              </div>
            </div>

            {/* Queue Summary Quick-View */}
            <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-5 text-xs space-y-3">
              <div className="flex items-center justify-between text-slate-200 font-semibold">
                <div className="flex items-center gap-2">
                  <Layers className="w-4 h-4 text-orange-400" />
                  <span>Broker Overview</span>
                </div>
                <span className="font-mono text-slate-400">{queues.length} Queues</span>
              </div>

              <div className="space-y-1.5 max-h-48 overflow-y-auto">
                {queues.length === 0 ? (
                  <div className="text-slate-500 py-2">No queues discovered.</div>
                ) : (
                  queues.slice(0, 6).map((q) => (
                    <div
                      key={q.name}
                      className="flex items-center justify-between p-2 rounded-lg bg-slate-950/60 border border-slate-800/60"
                    >
                      <span className="font-mono truncate max-w-[160px] text-slate-300">{q.name}</span>
                      <span className="font-mono text-orange-400 bg-orange-950/40 px-2 py-0.5 rounded text-[11px]">
                        {q.messages} msgs
                      </span>
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>
        </div>

        {/* Operation History Table */}
        <div className="pt-4">
          <HistoryTable
            operations={operationsHistory}
            onSelectOperation={(op) => setActiveOperation(op)}
          />
        </div>
      </main>

      {/* Modals */}
      <ConnectionModal
        isOpen={isSettingsOpen}
        onClose={() => setIsSettingsOpen(false)}
        config={config}
        onConfigSaved={(newCfg) => {
          setConfig(newCfg);
          loadInitialData();
        }}
      />

      <MessageSampleModal
        isOpen={!!sampleQueueName}
        onClose={() => setSampleQueueName(null)}
        queueName={sampleQueueName || ''}
        samples={samples}
        isLoading={isSampling}
        onSelectMessageId={(id) => {
          // You could automatically set target ID or copy
          navigator.clipboard.writeText(id);
          alert(`Copied ID to clipboard: ${id}`);
        }}
      />

      {pendingRequest && (
        <ConfirmationModal
          isOpen={true}
          onClose={() => setPendingRequest(null)}
          request={pendingRequest}
          sourceQueueDetails={sourceQueueDetails}
          onConfirm={handleConfirmOperation}
          isSubmitting={isSubmitting}
        />
      )}
    </div>
  );
};
