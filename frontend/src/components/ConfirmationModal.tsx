import React, { useState } from 'react';
import { AlertTriangle, ArrowRight, CheckCircle2, ShieldCheck, Trash2, X, Play } from 'lucide-react';
import { OperationRequest, QueueDetails } from '../types';

interface ConfirmationModalProps {
  isOpen: boolean;
  onClose: () => void;
  request: OperationRequest;
  sourceQueueDetails?: QueueDetails;
  onConfirm: () => void;
  isSubmitting: boolean;
}

export const ConfirmationModal: React.FC<ConfirmationModalProps> = ({
  isOpen,
  onClose,
  request,
  sourceQueueDetails,
  onConfirm,
  isSubmitting,
}) => {
  const [acknowledged, setAcknowledged] = useState(false);

  if (!isOpen) return null;

  const isDelete = request.operation_type === 'delete';
  const hasConsumers = (sourceQueueDetails?.consumers ?? 0) > 0;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in">
      <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-lg shadow-2xl overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800 bg-slate-950/60">
          <div className="flex items-center gap-2">
            <div
              className={`p-1.5 rounded-lg ${
                isDelete ? 'bg-rose-500/20 text-rose-400' : 'bg-orange-500/20 text-orange-400'
              }`}
            >
              {isDelete ? <Trash2 className="w-5 h-5" /> : <ArrowRight className="w-5 h-5" />}
            </div>
            <h2 className="font-semibold text-slate-100 text-lg">
              Confirm {isDelete ? 'Permanent Deletion' : 'Message Relocation'}
            </h2>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Summary Card */}
        <div className="p-6 space-y-4">
          <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-2.5 text-xs">
            <div className="flex items-center justify-between">
              <span className="text-slate-400">Operation:</span>
              <span
                className={`uppercase font-mono font-bold px-2 py-0.5 rounded ${
                  isDelete ? 'bg-rose-500/20 text-rose-300' : 'bg-orange-500/20 text-orange-300'
                }`}
              >
                {request.operation_type}
              </span>
            </div>

            <div className="flex items-center justify-between">
              <span className="text-slate-400">Source Queue:</span>
              <span className="font-mono text-slate-200 font-semibold">{request.source_queue}</span>
            </div>

            {!isDelete && request.destination_queue && (
              <div className="flex items-center justify-between">
                <span className="text-slate-400">Destination Queue:</span>
                <span className="font-mono text-emerald-400 font-semibold">{request.destination_queue}</span>
              </div>
            )}

            <div className="flex items-center justify-between">
              <span className="text-slate-400">Target Message ID:</span>
              <span className="font-mono text-orange-400 bg-orange-950/50 px-2 py-0.5 rounded border border-orange-800/40">
                {request.target_message_id}
              </span>
            </div>

            <div className="flex items-center justify-between">
              <span className="text-slate-400">Current Queue Messages:</span>
              <span className="font-mono text-slate-200">{sourceQueueDetails?.messages ?? 'Unknown'}</span>
            </div>
          </div>

          {/* Safety Warnings */}
          <div className="space-y-2 text-xs">
            {hasConsumers && (
              <div className="p-3 rounded-lg bg-amber-950/40 border border-amber-800/60 text-amber-200 flex items-start gap-2">
                <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
                <div>
                  <strong>Active Consumers Detected:</strong> Queue has {sourceQueueDetails?.consumers} active
                  consumer(s). For strict FIFO guarantees, ensure consumers are paused or stopped during operation.
                </div>
              </div>
            )}

            {isDelete && (
              <div className="p-3 rounded-lg bg-rose-950/40 border border-rose-800/60 text-rose-200 flex items-start gap-2">
                <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
                <div>
                  <strong>Irreversible Action:</strong> Once identified and purged, the target message cannot be
                  recovered from RabbitMQ.
                </div>
              </div>
            )}

            <div className="p-3 rounded-lg bg-slate-800/60 border border-slate-700/60 text-slate-300 flex items-start gap-2">
              <ShieldCheck className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
              <div>
                <strong>Zero Message Loss Safeguard:</strong> Messages are confirmed via publisher confirms and
                transferred through temporary queues before acknowledging from source. Auto-rollback is{' '}
                <span className="text-emerald-400 font-medium">
                  {request.auto_rollback_on_failure ? 'ENABLED' : 'DISABLED'}
                </span>
                .
              </div>
            </div>
          </div>

          {/* Checkbox Acknowledgment */}
          <div className="pt-2 flex items-start gap-2">
            <input
              type="checkbox"
              id="confirm-ack"
              checked={acknowledged}
              onChange={(e) => setAcknowledged(e.target.checked)}
              className="mt-0.5 rounded bg-slate-800 border-slate-700 text-orange-500 focus:ring-orange-500 focus:ring-offset-slate-900 w-4 h-4 cursor-pointer"
            />
            <label htmlFor="confirm-ack" className="text-xs text-slate-300 cursor-pointer select-none">
              I understand that the queue will be locked, drained, filtered, and restored to preserve the order of all
              remaining messages.
            </label>
          </div>
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-slate-800 bg-slate-950/40 flex items-center justify-end gap-3">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium transition"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={!acknowledged || isSubmitting}
            className={`px-4 py-2 rounded-lg text-white text-xs font-semibold shadow-lg flex items-center gap-2 transition disabled:opacity-50 disabled:cursor-not-allowed ${
              isDelete
                ? 'bg-rose-600 hover:bg-rose-500 shadow-rose-600/20'
                : 'bg-orange-600 hover:bg-orange-500 shadow-orange-600/20'
            }`}
          >
            <Play className="w-3.5 h-3.5" />
            <span>{isSubmitting ? 'Starting Operation...' : 'Start Operation'}</span>
          </button>
        </div>
      </div>
    </div>
  );
};
