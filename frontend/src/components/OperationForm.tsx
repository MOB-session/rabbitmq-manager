import React, { useState } from 'react';
import { ArrowRight, Trash2, Shield, AlertCircle, ChevronDown, ChevronUp, Sparkles } from 'lucide-react';
import { OperationRequest, OperationType, QueueDetails } from '../types';
import { QueueSelector } from './QueueSelector';

interface OperationFormProps {
  queues: QueueDetails[];
  onSubmit: (request: OperationRequest) => void;
  onInspectQueue: (queueName: string) => void;
  isInspectLoading: boolean;
}

export const OperationForm: React.FC<OperationFormProps> = ({
  queues,
  onSubmit,
  onInspectQueue,
  isInspectLoading,
}) => {
  const [operationType, setOperationType] = useState<OperationType>('delete');
  const [sourceQueue, setSourceQueue] = useState('');
  const [destinationQueue, setDestinationQueue] = useState('');
  const [targetMessageId, setTargetMessageId] = useState('');
  const [isolateProducers, setIsolateProducers] = useState(true);
  const [autoRollback, setAutoRollback] = useState(true);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);

    if (!sourceQueue) {
      setFormError('Please select a source queue.');
      return;
    }

    if (operationType === 'move' && !destinationQueue) {
      setFormError('Please select a destination queue for the MOVE operation.');
      return;
    }

    if (operationType === 'move' && sourceQueue === destinationQueue) {
      setFormError('Destination queue cannot be the same as the source queue.');
      return;
    }

    if (!targetMessageId.trim()) {
      setFormError('Please enter the target message ID.');
      return;
    }

    onSubmit({
      source_queue: sourceQueue,
      operation_type: operationType,
      target_message_id: targetMessageId.trim(),
      destination_queue: operationType === 'move' ? destinationQueue : undefined,
      isolate_producers: isolateProducers,
      auto_rollback_on_failure: autoRollback,
    });
  };

  const selectedSourceQueueDetails = queues.find((q) => q.name === sourceQueue);

  return (
    <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-6">
      {/* Operation Type Switcher */}
      <div>
        <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">
          Select Operation
        </label>
        <div className="grid grid-cols-2 gap-3 p-1 bg-slate-950 rounded-xl border border-slate-800">
          <button
            type="button"
            onClick={() => {
              setOperationType('delete');
              setFormError(null);
            }}
            className={`flex items-center justify-center gap-2 py-2.5 rounded-lg text-xs font-semibold transition ${
              operationType === 'delete'
                ? 'bg-rose-600 text-white shadow-lg shadow-rose-600/20'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <Trash2 className="w-4 h-4" />
            <span>Delete Message</span>
          </button>

          <button
            type="button"
            onClick={() => {
              setOperationType('move');
              setFormError(null);
            }}
            className={`flex items-center justify-center gap-2 py-2.5 rounded-lg text-xs font-semibold transition ${
              operationType === 'move'
                ? 'bg-orange-600 text-white shadow-lg shadow-orange-600/20'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <ArrowRight className="w-4 h-4" />
            <span>Move Message</span>
          </button>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="space-y-5">
        {/* Source Queue Selection */}
        <QueueSelector
          label="1. Source Queue"
          queues={queues}
          selectedQueue={sourceQueue}
          onSelectQueue={(q) => {
            setSourceQueue(q);
            setFormError(null);
          }}
          showInspectButton={true}
          onInspect={() => onInspectQueue(sourceQueue)}
          isInspectLoading={isInspectLoading}
          helpText="The queue containing the message you want to move or delete."
        />

        {/* Destination Queue Selection (if MOVE) */}
        {operationType === 'move' && (
          <QueueSelector
            label="2. Destination Queue"
            queues={queues}
            selectedQueue={destinationQueue}
            onSelectQueue={(q) => {
              setDestinationQueue(q);
              setFormError(null);
            }}
            disabledQueues={sourceQueue ? [sourceQueue] : []}
            helpText="The target queue where the extracted message will be republished."
          />
        )}

        {/* Target Message ID Input */}
        <div className="space-y-1.5">
          <div className="flex items-center justify-between">
            <label className="block text-xs font-semibold text-slate-200 uppercase tracking-wider">
              {operationType === 'move' ? '3.' : '2.'} Target Message ID
            </label>
            {sourceQueue && (
              <button
                type="button"
                onClick={() => onInspectQueue(sourceQueue)}
                className="text-[11px] text-orange-400 hover:text-orange-300 font-medium transition"
              >
                Find ID from queue head &rarr;
              </button>
            )}
          </div>
          <input
            type="text"
            value={targetMessageId}
            onChange={(e) => {
              setTargetMessageId(e.target.value);
              setFormError(null);
            }}
            placeholder="e.g. 550e8400-e29b-41d4-a716-446655440000 or custom ID"
            className="w-full px-3.5 py-2.5 rounded-xl bg-slate-950 border border-slate-800 text-slate-100 text-xs font-mono focus:outline-none focus:border-orange-500 transition placeholder:text-slate-600"
          />
          <p className="text-[11px] text-slate-400">
            Matches against AMQP standard <code className="text-slate-300">properties.message_id</code>, custom headers,
            or JSON payload <code className="text-slate-300">id</code>.
          </p>
        </div>

        {/* Advanced Safety Options Accordion */}
        <div className="border border-slate-800/80 rounded-xl bg-slate-950/40 overflow-hidden">
          <button
            type="button"
            onClick={() => setShowAdvanced(!showAdvanced)}
            className="w-full px-4 py-2.5 flex items-center justify-between text-xs text-slate-300 hover:text-white transition"
          >
            <div className="flex items-center gap-2">
              <Shield className="w-3.5 h-3.5 text-orange-400" />
              <span className="font-medium">Ordering & Safety Settings</span>
            </div>
            {showAdvanced ? <ChevronUp className="w-4 h-4 text-slate-500" /> : <ChevronDown className="w-4 h-4 text-slate-500" />}
          </button>

          {showAdvanced && (
            <div className="px-4 pb-4 pt-1 space-y-3 border-t border-slate-800/60 text-xs">
              <div className="flex items-start gap-2 pt-2">
                <input
                  type="checkbox"
                  id="isolate-producers"
                  checked={isolateProducers}
                  onChange={(e) => setIsolateProducers(e.target.checked)}
                  className="mt-0.5 rounded bg-slate-800 border-slate-700 text-orange-500 focus:ring-orange-500 focus:ring-offset-slate-900 w-4 h-4 cursor-pointer"
                />
                <div>
                  <label htmlFor="isolate-producers" className="font-medium text-slate-200 cursor-pointer">
                    Isolate Concurrent Producers via Ingress Buffer
                  </label>
                  <p className="text-[11px] text-slate-400 mt-0.5">
                    Diverts exchange bindings to an ingress buffer queue during execution so newly arriving messages are
                    not lost or interleaved.
                  </p>
                </div>
              </div>

              <div className="flex items-start gap-2">
                <input
                  type="checkbox"
                  id="auto-rollback"
                  checked={autoRollback}
                  onChange={(e) => setAutoRollback(e.target.checked)}
                  className="mt-0.5 rounded bg-slate-800 border-slate-700 text-orange-500 focus:ring-orange-500 focus:ring-offset-slate-900 w-4 h-4 cursor-pointer"
                />
                <div>
                  <label htmlFor="auto-rollback" className="font-medium text-slate-200 cursor-pointer">
                    Automatic Rollback on Failure
                  </label>
                  <p className="text-[11px] text-slate-400 mt-0.5">
                    If any error or network timeout occurs, automatically restores all drained messages back into the
                    source queue.
                  </p>
                </div>
              </div>
            </div>
          )}
        </div>

        {formError && (
          <div className="p-3 rounded-xl bg-rose-950/40 border border-rose-800/60 text-rose-300 text-xs flex items-center gap-2">
            <AlertCircle className="w-4 h-4 text-rose-400 shrink-0" />
            <span>{formError}</span>
          </div>
        )}

        <button
          type="submit"
          className="w-full py-3 rounded-xl bg-gradient-to-r from-orange-600 to-amber-600 hover:from-orange-500 hover:to-amber-500 text-white text-xs font-bold uppercase tracking-wider shadow-lg shadow-orange-600/20 transition flex items-center justify-center gap-2"
        >
          <Sparkles className="w-4 h-4" />
          <span>Review & Execute {operationType.toUpperCase()}</span>
        </button>
      </form>
    </div>
  );
};
