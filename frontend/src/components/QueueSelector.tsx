import React, { useState } from 'react';
import { Search, Eye, Lock, Users, Layers, AlertTriangle } from 'lucide-react';
import { QueueDetails } from '../types';

interface QueueSelectorProps {
  label: string;
  queues: QueueDetails[];
  selectedQueue: string;
  onSelectQueue: (queueName: string) => void;
  disabledQueues?: string[];
  showInspectButton?: boolean;
  onInspect?: () => void;
  isInspectLoading?: boolean;
  helpText?: string;
}

export const QueueSelector: React.FC<QueueSelectorProps> = ({
  label,
  queues,
  selectedQueue,
  onSelectQueue,
  disabledQueues = [],
  showInspectButton = false,
  onInspect,
  isInspectLoading = false,
  helpText,
}) => {
  const [searchTerm, setSearchTerm] = useState('');

  const filteredQueues = queues.filter((q) =>
    q.name.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const selectedQueueDetails = queues.find((q) => q.name === selectedQueue);

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <label className="block text-xs font-semibold text-slate-200 uppercase tracking-wider">
          {label}
        </label>
        {showInspectButton && selectedQueue && (
          <button
            type="button"
            onClick={onInspect}
            disabled={isInspectLoading}
            className="flex items-center gap-1.5 text-xs text-orange-400 hover:text-orange-300 font-medium transition disabled:opacity-50"
          >
            <Eye className="w-3.5 h-3.5" />
            <span>{isInspectLoading ? 'Sampling...' : 'Inspect Queue Head'}</span>
          </button>
        )}
      </div>

      {helpText && <p className="text-[11px] text-slate-400">{helpText}</p>}

      {/* Search Filter */}
      <div className="relative">
        <Search className="w-4 h-4 text-slate-500 absolute left-3 top-2.5" />
        <input
          type="text"
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          placeholder="Filter queues by name..."
          className="w-full pl-9 pr-3 py-2 rounded-lg bg-slate-900 border border-slate-800 text-slate-100 text-xs focus:outline-none focus:border-orange-500 transition placeholder:text-slate-500"
        />
      </div>

      {/* Queue List Select */}
      <div className="max-h-52 overflow-y-auto rounded-xl border border-slate-800 bg-slate-950/60 divide-y divide-slate-800/60">
        {filteredQueues.length === 0 ? (
          <div className="p-4 text-center text-xs text-slate-500">
            {queues.length === 0 ? 'No queues found on this vhost.' : 'No queues match filter.'}
          </div>
        ) : (
          filteredQueues.map((q) => {
            const isSelected = q.name === selectedQueue;
            const isDisabled = disabledQueues.includes(q.name) || q.is_locked;

            return (
              <div
                key={q.name}
                onClick={() => {
                  if (!isDisabled) onSelectQueue(q.name);
                }}
                className={`p-3 flex items-center justify-between transition cursor-pointer ${
                  isSelected
                    ? 'bg-orange-600/10 border-l-4 border-l-orange-500 text-slate-100'
                    : isDisabled
                    ? 'opacity-40 cursor-not-allowed bg-slate-900/40 text-slate-400'
                    : 'hover:bg-slate-900 text-slate-300'
                }`}
              >
                <div className="flex items-center gap-2 min-w-0">
                  <div
                    className={`w-2 h-2 rounded-full shrink-0 ${
                      isSelected ? 'bg-orange-500' : 'bg-slate-600'
                    }`}
                  />
                  <span className="font-mono text-xs truncate font-medium">{q.name}</span>
                  {q.type && q.type !== 'classic' && (
                    <span className="text-[10px] uppercase font-mono px-1.5 py-0.2 rounded bg-purple-500/10 text-purple-400 border border-purple-500/20">
                      {q.type}
                    </span>
                  )}
                </div>

                <div className="flex items-center gap-2 shrink-0 text-[11px]">
                  {q.is_locked ? (
                    <span className="flex items-center gap-1 text-amber-400 bg-amber-500/10 px-2 py-0.5 rounded font-medium">
                      <Lock className="w-3 h-3" /> Locked
                    </span>
                  ) : (
                    <>
                      {q.consumers > 0 && (
                        <span
                          className="flex items-center gap-1 text-amber-300/90 bg-amber-950/40 px-2 py-0.5 rounded border border-amber-800/40"
                          title="Active consumers detected"
                        >
                          <Users className="w-3 h-3" />
                          <span>{q.consumers}</span>
                        </span>
                      )}
                      <span className="font-mono text-slate-400 bg-slate-800/80 px-2 py-0.5 rounded">
                        {q.messages} msg{q.messages === 1 ? '' : 's'}
                      </span>
                    </>
                  )}
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* Selected Queue Context / Warnings */}
      {selectedQueueDetails && (
        <div className="p-2.5 rounded-lg bg-slate-900/70 border border-slate-800 text-xs space-y-1">
          <div className="flex items-center justify-between text-slate-400">
            <span>Type: <strong className="text-slate-200 capitalize">{selectedQueueDetails.type}</strong></span>
            <span>Messages: <strong className="text-slate-200 font-mono">{selectedQueueDetails.messages}</strong></span>
            <span>Consumers: <strong className="text-slate-200 font-mono">{selectedQueueDetails.consumers}</strong></span>
          </div>

          {selectedQueueDetails.consumers > 0 && (
            <div className="flex items-start gap-1.5 text-amber-300 text-[11px] pt-1 border-t border-slate-800">
              <AlertTriangle className="w-3.5 h-3.5 shrink-0 mt-0.5" />
              <span>
                <strong>Warning:</strong> Active consumers ({selectedQueueDetails.consumers}) are attached to this queue.
                Pause consumers before running to prevent them from consuming messages during the drain phase.
              </span>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
