import React from 'react';
import { Server, Settings, ShieldAlert, RefreshCw } from 'lucide-react';
import { RabbitMQConfig, SystemStatus } from '../types';

interface NavbarProps {
  config: RabbitMQConfig | null;
  systemStatus: SystemStatus | null;
  onOpenSettings: () => void;
  onRefresh: () => void;
  isRefreshing: boolean;
}

export const Navbar: React.FC<NavbarProps> = ({
  config,
  systemStatus,
  onOpenSettings,
  onRefresh,
  isRefreshing,
}) => {
  const isHealthy = systemStatus?.status === 'healthy';
  const hasRecovery = (systemStatus?.recovery_needed_count ?? 0) > 0;
  const lockedCount = systemStatus?.locked_queues?.length ?? 0;

  return (
    <header className="border-b border-slate-800 bg-slate-900/80 backdrop-blur sticky top-0 z-40">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-orange-600/20 border border-orange-500/30 flex items-center justify-center text-orange-500 shadow-lg shadow-orange-500/10">
            <Server className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="font-bold text-slate-100 text-lg leading-tight">RabbitMQ Manager</h1>
              <span className="text-[10px] font-mono tracking-wide uppercase px-1.5 py-0.5 rounded bg-orange-500/10 text-orange-400 border border-orange-500/20">
                v4.1.0 Ready
              </span>
            </div>
            <p className="text-xs text-slate-400">Selective Message Purge & Move Orchestrator</p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {/* Status Pills */}
          <div className="hidden sm:flex items-center gap-2 text-xs">
            <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-slate-800/80 border border-slate-700/60 text-slate-300">
              <span className={`w-2 h-2 rounded-full ${isHealthy ? 'bg-emerald-500 animate-pulse' : 'bg-rose-500'}`} />
              <span className="font-mono">{config ? `${config.host}:${config.port}` : 'Connecting...'}</span>
              <span className="text-slate-500">({config?.vhost || '/'})</span>
            </div>

            {lockedCount > 0 && (
              <div className="flex items-center gap-1 px-2.5 py-1 rounded-full bg-amber-500/10 border border-amber-500/30 text-amber-400">
                <span className="w-1.5 h-1.5 rounded-full bg-amber-400" />
                <span>{lockedCount} Queue{lockedCount > 1 ? 's' : ''} Locked</span>
              </div>
            )}

            {hasRecovery && (
              <div className="flex items-center gap-1 px-2.5 py-1 rounded-full bg-rose-500/20 border border-rose-500/40 text-rose-300 animate-bounce">
                <ShieldAlert className="w-3.5 h-3.5" />
                <span>Recovery Needed ({systemStatus?.recovery_needed_count})</span>
              </div>
            )}
          </div>

          {/* Action Buttons */}
          <button
            onClick={onRefresh}
            disabled={isRefreshing}
            className="p-2 rounded-lg bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-300 hover:text-white transition disabled:opacity-50"
            title="Refresh Queues & Status"
          >
            <RefreshCw className={`w-4 h-4 ${isRefreshing ? 'animate-spin' : ''}`} />
          </button>

          <button
            onClick={onOpenSettings}
            className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-200 text-xs font-medium transition"
          >
            <Settings className="w-3.5 h-3.5 text-slate-400" />
            <span>Connection</span>
          </button>
        </div>
      </div>
    </header>
  );
};
