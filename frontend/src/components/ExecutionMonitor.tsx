import React, { useEffect, useRef, useState } from 'react';
import {
  CheckCircle2,
  Clock,
  Loader2,
  AlertCircle,
  RotateCcw,
  Terminal,
  ArrowRight,
  ShieldAlert,
  Layers,
  Check,
  XCircle,
} from 'lucide-react';
import { OperationPhase, OperationRecord, OperationStatus } from '../types';

interface ExecutionMonitorProps {
  operation: OperationRecord;
  onUpdate: (updated: OperationRecord) => void;
  onClose: () => void;
}

const PHASES_LIST: { id: OperationPhase; label: string; desc: string }[] = [
  { id: 'initializing', label: '1. Initialize', desc: 'Create temporary queues' },
  { id: 'diverting_traffic', label: '2. Divert Traffic', desc: 'Isolate live producers to buffer' },
  { id: 'draining_to_temp1', label: '3. Drain to Temp 1', desc: 'Transfer source queue messages' },
  { id: 'filtering_to_temp2', label: '4. Filter & Route', desc: 'Inspect IDs & move/delete target' },
  { id: 'restoring_source', label: '5. Restore Source', desc: 'Return non-target messages in order' },
  { id: 'flushing_buffer', label: '6. Flush Buffer', desc: 'Append live messages from buffer' },
  { id: 'completed', label: '7. Completed', desc: 'Temporary queues cleaned up' },
];

export const ExecutionMonitor: React.FC<ExecutionMonitorProps> = ({
  operation,
  onUpdate,
  onClose,
}) => {
  const [liveRecord, setLiveRecord] = useState<OperationRecord>(operation);
  const logContainerRef = useRef<HTMLDivElement>(null);

  // Connect to Server-Sent Events (SSE) stream for real-time updates
  useEffect(() => {
    const eventSource = new EventSource(`/api/operations/${operation.id}/events`);

    eventSource.onmessage = (event) => {
      try {
        const data: OperationRecord = JSON.parse(event.data);
        setLiveRecord(data);
        onUpdate(data);
      } catch (err) {
        console.error('Failed to parse SSE event:', err);
      }
    };

    eventSource.onerror = (err) => {
      console.warn('SSE stream closed or error occurred');
      eventSource.close();
    };

    return () => {
      eventSource.close();
    };
  }, [operation.id]);

  // Auto-scroll logs to bottom
  useEffect(() => {
    if (logContainerRef.current) {
      logContainerRef.current.scrollTop = logContainerRef.current.scrollHeight;
    }
  }, [liveRecord.logs]);

  const isCompleted = liveRecord.status === 'completed';
  const isFailed = liveRecord.status === 'failed';
  const isRolledBack = liveRecord.status === 'rolled_back';
  const isFinished = isCompleted || isFailed || isRolledBack;

  // Compute active phase index
  const getPhaseStatus = (phaseId: OperationPhase) => {
    const order: OperationPhase[] = [
      'idle',
      'initializing',
      'diverting_traffic',
      'draining_to_temp1',
      'filtering_to_temp2',
      'restoring_source',
      'flushing_buffer',
      'cleaning_up',
      'completed',
    ];
    const currentIndex = order.indexOf(liveRecord.phase);
    const stepIndex = order.indexOf(phaseId);

    if (isCompleted) return 'completed';
    if (isFailed && liveRecord.phase === phaseId) return 'failed';
    if (stepIndex < currentIndex) return 'completed';
    if (stepIndex === currentIndex) return 'active';
    return 'pending';
  };

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-2xl space-y-6 animate-in fade-in">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-800">
        <div>
          <div className="flex items-center gap-2">
            <span className="font-mono text-xs px-2.5 py-1 rounded bg-slate-800 text-slate-300 font-semibold">
              OP: {liveRecord.id}
            </span>
            <span
              className={`font-mono text-xs uppercase px-2.5 py-1 rounded font-bold ${
                isCompleted
                  ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                  : isFailed
                  ? 'bg-rose-500/20 text-rose-400 border border-rose-500/30'
                  : isRolledBack
                  ? 'bg-amber-500/20 text-amber-400 border border-amber-500/30'
                  : 'bg-orange-500/20 text-orange-400 border border-orange-500/30 animate-pulse'
              }`}
            >
              {liveRecord.status}
            </span>
            <span className="text-xs text-slate-400 font-mono">
              Target ID: <span className="text-orange-400">{liveRecord.request.target_message_id}</span>
            </span>
          </div>
          <h2 className="text-base font-bold text-slate-100 mt-1">
            {liveRecord.request.operation_type.toUpperCase()} from queue{' '}
            <span className="font-mono text-orange-400">{liveRecord.request.source_queue}</span>
            {liveRecord.request.destination_queue && (
              <> to <span className="font-mono text-emerald-400">{liveRecord.request.destination_queue}</span></>
            )}
          </h2>
        </div>

        {isFinished && (
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold transition"
          >
            Done / Close Monitor
          </button>
        )}
      </div>

      {/* Pipeline Stage Stepper */}
      <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-2">
        {PHASES_LIST.map((step) => {
          const status = getPhaseStatus(step.id);
          return (
            <div
              key={step.id}
              className={`p-3 rounded-xl border text-xs transition ${
                status === 'completed'
                  ? 'bg-emerald-950/20 border-emerald-800/40 text-emerald-300'
                  : status === 'active'
                  ? 'bg-orange-950/30 border-orange-500 text-orange-200 ring-2 ring-orange-500/20 animate-pulse'
                  : status === 'failed'
                  ? 'bg-rose-950/30 border-rose-600 text-rose-300'
                  : 'bg-slate-950/40 border-slate-800 text-slate-500'
              }`}
            >
              <div className="flex items-center justify-between mb-1">
                <span className="font-semibold">{step.label}</span>
                {status === 'completed' && <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />}
                {status === 'active' && <Loader2 className="w-3.5 h-3.5 text-orange-400 animate-spin" />}
                {status === 'failed' && <XCircle className="w-3.5 h-3.5 text-rose-400" />}
              </div>
              <div className="text-[10px] opacity-75">{step.desc}</div>
            </div>
          );
        })}
      </div>

      {/* Metrics Dashboard */}
      <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-3">
        <div className="p-3 rounded-xl bg-slate-950 border border-slate-800">
          <div className="text-[10px] uppercase font-semibold text-slate-500">Initial Queue</div>
          <div className="text-xl font-bold font-mono text-slate-200 mt-1">{liveRecord.initial_count}</div>
        </div>

        <div className="p-3 rounded-xl bg-slate-950 border border-slate-800">
          <div className="text-[10px] uppercase font-semibold text-slate-500">In Temp 1</div>
          <div className="text-xl font-bold font-mono text-orange-400 mt-1">{liveRecord.transferred_to_temp1}</div>
        </div>

        <div className="p-3 rounded-xl bg-slate-950 border border-slate-800">
          <div className="text-[10px] uppercase font-semibold text-slate-500">Inspected</div>
          <div className="text-xl font-bold font-mono text-slate-200 mt-1">{liveRecord.inspected_count}</div>
        </div>

        <div className="p-3 rounded-xl bg-slate-950 border border-slate-800">
          <div className="text-[10px] uppercase font-semibold text-slate-500">Target Match</div>
          <div className="mt-1">
            {liveRecord.target_found ? (
              <span className="text-xs font-bold font-mono px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
                FOUND
              </span>
            ) : (
              <span className="text-xs font-mono text-slate-500">Scanning...</span>
            )}
          </div>
        </div>

        <div className="p-3 rounded-xl bg-slate-950 border border-slate-800">
          <div className="text-[10px] uppercase font-semibold text-slate-500">Retained (Temp 2)</div>
          <div className="text-xl font-bold font-mono text-purple-400 mt-1">{liveRecord.retained_count}</div>
        </div>

        <div className="p-3 rounded-xl bg-slate-950 border border-slate-800">
          <div className="text-[10px] uppercase font-semibold text-slate-500">Restored</div>
          <div className="text-xl font-bold font-mono text-emerald-400 mt-1">{liveRecord.restored_count}</div>
        </div>

        <div className="p-3 rounded-xl bg-slate-950 border border-slate-800">
          <div className="text-[10px] uppercase font-semibold text-slate-500">Buffered Traffic</div>
          <div className="text-xl font-bold font-mono text-blue-400 mt-1">{liveRecord.buffer_count}</div>
        </div>
      </div>

      {/* Terminal Live Logs */}
      <div className="rounded-xl border border-slate-800 bg-slate-950 overflow-hidden shadow-inner">
        <div className="px-4 py-2 border-b border-slate-800/80 bg-slate-900/60 flex items-center justify-between text-xs text-slate-400">
          <div className="flex items-center gap-2">
            <Terminal className="w-3.5 h-3.5 text-orange-400" />
            <span className="font-mono font-medium">Execution Event Log</span>
          </div>
          <span className="font-mono text-[11px] text-slate-500">{liveRecord.logs.length} events</span>
        </div>

        <div
          ref={logContainerRef}
          className="p-4 font-mono text-xs text-slate-300 max-h-56 overflow-y-auto space-y-1 bg-black/40"
        >
          {liveRecord.logs.length === 0 ? (
            <div className="text-slate-600 italic">Awaiting execution output...</div>
          ) : (
            liveRecord.logs.map((log, index) => {
              const isError = log.includes('ERROR') || log.includes('CRITICAL');
              const isSuccess = log.includes('SUCCESS') || log.includes('MATCH FOUND');
              const isWarning = log.includes('WARNING');
              return (
                <div
                  key={index}
                  className={`leading-relaxed ${
                    isError
                      ? 'text-rose-400 font-semibold'
                      : isSuccess
                      ? 'text-emerald-400 font-semibold'
                      : isWarning
                      ? 'text-amber-300'
                      : 'text-slate-300'
                  }`}
                >
                  {log}
                </div>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
};
