import React from 'react';
import { X, Search, Check, Copy, Tag, Clock, Layers } from 'lucide-react';
import { MessageSample } from '../types';

interface MessageSampleModalProps {
  isOpen: boolean;
  onClose: () => void;
  queueName: string;
  samples: MessageSample[];
  isLoading: boolean;
  onSelectMessageId: (messageId: string) => void;
}

export const MessageSampleModal: React.FC<MessageSampleModalProps> = ({
  isOpen,
  onClose,
  queueName,
  samples,
  isLoading,
  onSelectMessageId,
}) => {
  const [copiedId, setCopiedId] = React.useState<string | null>(null);

  if (!isOpen) return null;

  const handleCopy = (id: string) => {
    navigator.clipboard.writeText(id);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-sm animate-in fade-in">
      <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-2xl max-h-[85vh] shadow-2xl flex flex-col overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800">
          <div>
            <div className="flex items-center gap-2">
              <Search className="w-5 h-5 text-orange-500" />
              <h2 className="font-semibold text-slate-100 text-lg">Inspect Queue Head</h2>
            </div>
            <p className="text-xs text-slate-400">
              Sampled up to {samples.length} messages from queue{' '}
              <span className="font-mono text-orange-400 font-semibold">{queueName}</span> (non-destructive inspection)
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 overflow-y-auto space-y-4 flex-1">
          {isLoading ? (
            <div className="text-center py-12 text-slate-400 text-sm">Loading sampled messages...</div>
          ) : samples.length === 0 ? (
            <div className="text-center py-12 text-slate-400 text-sm">
              No messages found or queue is currently empty.
            </div>
          ) : (
            samples.map((msg, index) => {
              const msgId = msg.properties.message_id || msg.properties.correlation_id || '';
              return (
                <div
                  key={index}
                  className="p-4 rounded-xl bg-slate-950/60 border border-slate-800 hover:border-slate-700 transition space-y-3"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-mono px-2 py-0.5 rounded bg-slate-800 text-slate-300">
                        #{index + 1}
                      </span>
                      {msgId ? (
                        <div className="flex items-center gap-1.5 font-mono text-xs text-orange-400 bg-orange-950/40 px-2.5 py-0.5 rounded border border-orange-800/40">
                          <Tag className="w-3 h-3" />
                          <span>ID: {msgId}</span>
                        </div>
                      ) : (
                        <span className="text-xs text-slate-500 italic">No message_id property</span>
                      )}
                    </div>

                    <div className="flex items-center gap-2">
                      {msgId && (
                        <>
                          <button
                            onClick={() => handleCopy(msgId)}
                            className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs transition"
                            title="Copy ID"
                          >
                            {copiedId === msgId ? (
                              <Check className="w-3.5 h-3.5 text-emerald-400" />
                            ) : (
                              <Copy className="w-3.5 h-3.5" />
                            )}
                          </button>
                          <button
                            onClick={() => {
                              onSelectMessageId(msgId);
                              onClose();
                            }}
                            className="px-2.5 py-1 rounded-lg bg-orange-600 hover:bg-orange-500 text-white text-xs font-medium transition"
                          >
                            Target this ID
                          </button>
                        </>
                      )}
                    </div>
                  </div>

                  {/* Properties metadata */}
                  <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 text-[11px] text-slate-400 bg-slate-900/60 p-2.5 rounded-lg border border-slate-800/50">
                    <div>
                      <span className="text-slate-500">Routing Key: </span>
                      <span className="font-mono text-slate-300">{msg.routing_key || '—'}</span>
                    </div>
                    <div>
                      <span className="text-slate-500">Payload Size: </span>
                      <span className="font-mono text-slate-300">{msg.payload_bytes} bytes</span>
                    </div>
                    <div>
                      <span className="text-slate-500">Delivery Mode: </span>
                      <span className="font-mono text-slate-300">
                        {msg.properties.delivery_mode === 2 ? 'Persistent' : 'Transient'}
                      </span>
                    </div>
                  </div>

                  {/* Payload Preview */}
                  <div>
                    <div className="text-[11px] font-medium text-slate-400 mb-1">Payload:</div>
                    <pre className="text-xs font-mono bg-slate-900 p-3 rounded-lg border border-slate-800 text-slate-200 overflow-x-auto max-h-32">
                      {msg.payload}
                    </pre>
                  </div>
                </div>
              );
            })
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-3 border-t border-slate-800 flex justify-end bg-slate-950/40">
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium transition"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};
