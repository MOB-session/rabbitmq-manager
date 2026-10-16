import React, { useState } from 'react';
import { History, Eye, ArrowRight, Trash2, CheckCircle2, XCircle, RotateCcw, AlertTriangle } from 'lucide-react';
import { OperationRecord } from '../types';

interface HistoryTableProps {
  operations: OperationRecord[];
  onSelectOperation: (op: OperationRecord) => void;
}

export const HistoryTable: React.FC<HistoryTableProps> = ({
  operations,
  onSelectOperation,
}) => {
  const [selectedLogOp, setSelectedLogOp] = useState<OperationRecord | null>(null);

  if (operations.length === 0) {
    return (
      <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-8 text-center text-slate-500 text-sm">
        <History className="w-6 h-6 mx-auto mb-2 text-slate-600" />
        No past operations recorded yet.
      </div>
    );
  }

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-2xl shadow-xl overflow-hidden">
      <div className="px-6 py-4 border-b border-slate-800 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <History className="w-5 h-5 text-orange-400" />
          <h3 className="font-semibold text-slate-100 text-sm">Operation History & Audit Log</h3>
        </div>
        <span className="text-xs text-slate-500 font-mono">{operations.length} records</span>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs">
          <thead className="bg-slate-950/80 text-slate-400 border-b border-slate-800 uppercase tracking-wider font-semibold text-[10px]">
            <tr>
              <th className="px-6 py-3">Operation ID</th>
              <th className="px-6 py-3">Timestamp</th>
              <th className="px-6 py-3">Type</th>
              <th className="px-6 py-3">Source Queue</th>
              <th className="px-6 py-3">Target ID</th>
              <th className="px-6 py-3">Outcome</th>
              <th className="px-6 py-3">Messages</th>
              <th className="px-6 py-3 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/60 font-mono text-slate-300">
            {operations.map((op) => {
              const isDelete = op.request.operation_type === 'delete';
              const isSuccess = op.status === 'completed';
              const isFailed = op.status === 'failed';
              const isRolledBack = op.status === 'rolled_back';

              return (
                <tr key={op.id} className="hover:bg-slate-800/40 transition">
                  <td className="px-6 py-3.5 font-bold text-slate-200">{op.id}</td>
                  <td className="px-6 py-3.5 text-slate-400 text-[11px] font-sans">
                    {op.created_at.slice(0, 19).replace('T', ' ')}
                  </td>
                  <td className="px-6 py-3.5">
                    <span
                      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold uppercase ${
                        isDelete
                          ? 'bg-rose-500/10 text-rose-400 border border-rose-500/20'
                          : 'bg-orange-500/10 text-orange-400 border border-orange-500/20'
                      }`}
                    >
                      {isDelete ? <Trash2 className="w-2.5 h-2.5" /> : <ArrowRight className="w-2.5 h-2.5" />}
                      {op.request.operation_type}
                    </span>
                  </td>
                  <td className="px-6 py-3.5 text-slate-200">{op.request.source_queue}</td>
                  <td className="px-6 py-3.5 text-orange-400 truncate max-w-[140px]" title={op.request.target_message_id}>
                    {op.request.target_message_id}
                  </td>
                  <td className="px-6 py-3.5">
                    <span
                      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] uppercase font-semibold ${
                        isSuccess
                          ? 'bg-emerald-500/20 text-emerald-400'
                          : isFailed
                          ? 'bg-rose-500/20 text-rose-400'
                          : isRolledBack
                          ? 'bg-amber-500/20 text-amber-400'
                          : 'bg-slate-800 text-slate-400'
                      }`}
                    >
                      {isSuccess && <CheckCircle2 className="w-3 h-3" />}
                      {isFailed && <XCircle className="w-3 h-3" />}
                      {isRolledBack && <RotateCcw className="w-3 h-3" />}
                      {op.status}
                    </span>
                  </td>
                  <td className="px-6 py-3.5 text-slate-400 text-[11px]">
                    Retained: <span className="text-slate-200 font-semibold">{op.retained_count}</span> | Restored:{' '}
                    <span className="text-slate-200 font-semibold">{op.restored_count}</span>
                  </td>
                  <td className="px-6 py-3.5 text-right font-sans">
                    <button
                      onClick={() => onSelectOperation(op)}
                      className="px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium transition inline-flex items-center gap-1"
                    >
                      <Eye className="w-3.5 h-3.5 text-slate-400" />
                      <span>Details</span>
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
};
