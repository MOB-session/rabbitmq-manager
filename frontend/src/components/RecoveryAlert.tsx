import React, { useState } from 'react';
import { AlertTriangle, RotateCcw, Trash2, Loader2, ArrowRight } from 'lucide-react';
import { OperationRecord, RecoveryAction } from '../types';
import { api } from '../services/api';

interface RecoveryAlertProps {
  recoveryOperations: OperationRecord[];
  onRecoveryComplete: () => void;
}

export const RecoveryAlert: React.FC<RecoveryAlertProps> = ({
  recoveryOperations,
  onRecoveryComplete,
}) => {
  const [processingId, setProcessingId] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  if (recoveryOperations.length === 0) return null;

  const handleAction = async (opId: string, action: RecoveryAction) => {
    setProcessingId(opId);
    setActionError(null);
    try {
      await api.recoverOperation(opId, action);
      onRecoveryComplete();
    } catch (err: any) {
      setActionError(err.message || 'Recovery failed');
    } finally {
      setProcessingId(null);
    }
  };

  return (
    <div className="mb-6 space-y-3">
      {recoveryOperations.map((op) => (
        <div
          key={op.id}
          className="p-4 rounded-xl border border-rose-600/40 bg-gradient-to-r from-rose-950/60 to-rose-900/30 text-rose-200 shadow-xl shadow-rose-950/20"
        >
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div className="flex items-start gap-3">
              <div className="p-2 rounded-lg bg-rose-500/20 text-rose-400 mt-0.5 shrink-0">
                <AlertTriangle className="w-5 h-5" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h3 className="font-semibold text-rose-100 text-sm">
                    Operation {op.id} Interrupted — Recovery Required
                  </h3>
                  <span className="text-[10px] uppercase font-mono px-2 py-0.5 rounded bg-rose-500/20 text-rose-300 border border-rose-500/30">
                    Source: {op.request.source_queue}
                  </span>
                </div>
                <p className="text-xs text-rose-300/80 mt-1">
                  The operation failed or was interrupted during phase{' '}
                  <span className="font-mono text-rose-200 uppercase font-semibold">{op.phase}</span>. Temporary
                  queues (<span className="font-mono text-white/90">{op.temp1_queue}</span>,{' '}
                  <span className="font-mono text-white/90">{op.temp2_queue}</span>
                  {op.buffer_queue && <>, <span className="font-mono text-white/90">{op.buffer_queue}</span></>}) are
                  preserved to guarantee zero message loss.
                </p>
                {op.error_message && (
                  <p className="text-[11px] font-mono text-rose-400 mt-1 bg-black/30 px-2 py-1 rounded inline-block">
                    Reason: {op.error_message}
                  </p>
                )}
              </div>
            </div>

            <div className="flex items-center gap-2 shrink-0">
              <button
                onClick={() => handleAction(op.id, 'rollback')}
                disabled={processingId === op.id}
                className="px-3.5 py-2 rounded-lg bg-rose-600 hover:bg-rose-500 text-white text-xs font-semibold shadow-lg shadow-rose-600/20 flex items-center gap-1.5 transition disabled:opacity-50"
              >
                {processingId === op.id ? (
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                ) : (
                  <RotateCcw className="w-3.5 h-3.5" />
                )}
                <span>Rollback to Source</span>
              </button>

              <button
                onClick={() => handleAction(op.id, 'discard_temps')}
                disabled={processingId === op.id}
                className="px-3 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white border border-slate-700 text-xs font-medium flex items-center gap-1.5 transition disabled:opacity-50"
                title="Only use if you have verified that no unprocessed messages remain"
              >
                <Trash2 className="w-3.5 h-3.5 text-slate-400" />
                <span>Discard Temps</span>
              </button>
            </div>
          </div>

          {actionError && (
            <div className="mt-2 text-xs text-rose-400 bg-black/40 px-3 py-1.5 rounded-lg border border-rose-800/40">
              {actionError}
            </div>
          )}
        </div>
      ))}
    </div>
  );
};
