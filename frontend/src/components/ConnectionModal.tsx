import React, { useState, useEffect } from 'react';
import { X, CheckCircle2, AlertCircle, Loader2, Save, Wifi } from 'lucide-react';
import { ConnectionTestResult, RabbitMQConfig } from '../types';
import { api } from '../services/api';

interface ConnectionModalProps {
  isOpen: boolean;
  onClose: () => void;
  config: RabbitMQConfig | null;
  onConfigSaved: (newConfig: RabbitMQConfig) => void;
}

export const ConnectionModal: React.FC<ConnectionModalProps> = ({
  isOpen,
  onClose,
  config,
  onConfigSaved,
}) => {
  const [formData, setFormData] = useState<RabbitMQConfig>({
    host: 'localhost',
    port: 5672,
    management_port: 15672,
    vhost: '/',
    username: 'guest',
    password: '',
    use_ssl: false,
  });

  const [isTesting, setIsTesting] = useState(false);
  const [testResult, setTestResult] = useState<ConnectionTestResult | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  useEffect(() => {
    if (config) {
      setFormData(config);
    }
  }, [config]);

  if (!isOpen) return null;

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value, type, checked } = e.target;
    setFormData((prev) => ({
      ...prev,
      [name]: type === 'checkbox' ? checked : type === 'number' ? parseInt(value) || 0 : value,
    }));
    setTestResult(null);
    setSaveError(null);
  };

  const handleTest = async () => {
    setIsTesting(true);
    setTestResult(null);
    try {
      const res = await api.testConnection(formData);
      setTestResult(res);
    } catch (err: any) {
      setTestResult({
        success: false,
        message: err.message || 'Failed to connect',
        amqp_connected: false,
      });
    } finally {
      setIsTesting(false);
    }
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSaving(true);
    setSaveError(null);
    try {
      const updated = await api.updateConfig(formData);
      onConfigSaved(updated);
      onClose();
    } catch (err: any) {
      setSaveError(err.message || 'Failed to save settings');
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-in fade-in">
      <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-lg shadow-2xl overflow-hidden">
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800">
          <div className="flex items-center gap-2">
            <Wifi className="w-5 h-5 text-orange-500" />
            <h2 className="font-semibold text-slate-100 text-lg">RabbitMQ Connection Settings</h2>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={handleSave} className="p-6 space-y-4">
          <div className="grid grid-cols-3 gap-3">
            <div className="col-span-2">
              <label className="block text-xs font-medium text-slate-300 mb-1">Host / IP</label>
              <input
                type="text"
                name="host"
                value={formData.host}
                onChange={handleChange}
                required
                className="w-full px-3 py-2 rounded-lg bg-slate-800/80 border border-slate-700 text-slate-100 text-sm focus:outline-none focus:border-orange-500 transition"
                placeholder="localhost or 127.0.0.1"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1">AMQP Port</label>
              <input
                type="number"
                name="port"
                value={formData.port}
                onChange={handleChange}
                required
                className="w-full px-3 py-2 rounded-lg bg-slate-800/80 border border-slate-700 text-slate-100 text-sm focus:outline-none focus:border-orange-500 transition font-mono"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1">Management HTTP Port</label>
              <input
                type="number"
                name="management_port"
                value={formData.management_port}
                onChange={handleChange}
                required
                className="w-full px-3 py-2 rounded-lg bg-slate-800/80 border border-slate-700 text-slate-100 text-sm focus:outline-none focus:border-orange-500 transition font-mono"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1">Virtual Host</label>
              <input
                type="text"
                name="vhost"
                value={formData.vhost}
                onChange={handleChange}
                required
                className="w-full px-3 py-2 rounded-lg bg-slate-800/80 border border-slate-700 text-slate-100 text-sm focus:outline-none focus:border-orange-500 transition font-mono"
                placeholder="/"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1">Username</label>
              <input
                type="text"
                name="username"
                value={formData.username}
                onChange={handleChange}
                required
                className="w-full px-3 py-2 rounded-lg bg-slate-800/80 border border-slate-700 text-slate-100 text-sm focus:outline-none focus:border-orange-500 transition"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1">Password</label>
              <input
                type="password"
                name="password"
                value={formData.password}
                onChange={handleChange}
                className="w-full px-3 py-2 rounded-lg bg-slate-800/80 border border-slate-700 text-slate-100 text-sm focus:outline-none focus:border-orange-500 transition"
                placeholder="••••••••"
              />
            </div>
          </div>

          <div className="flex items-center gap-2 pt-1">
            <input
              type="checkbox"
              id="use_ssl"
              name="use_ssl"
              checked={formData.use_ssl}
              onChange={handleChange}
              className="rounded bg-slate-800 border-slate-700 text-orange-500 focus:ring-orange-500 focus:ring-offset-slate-900 w-4 h-4"
            />
            <label htmlFor="use_ssl" className="text-xs text-slate-300 cursor-pointer">
              Use TLS / SSL Connection (amqps & https)
            </label>
          </div>

          {/* Test Connection Results */}
          {testResult && (
            <div
              className={`p-3 rounded-xl border text-xs ${
                testResult.success
                  ? 'bg-emerald-950/40 border-emerald-800/60 text-emerald-300'
                  : 'bg-rose-950/40 border-rose-800/60 text-rose-300'
              }`}
            >
              <div className="flex items-start gap-2">
                {testResult.success ? (
                  <CheckCircle2 className="w-4 h-4 text-emerald-400 mt-0.5 shrink-0" />
                ) : (
                  <AlertCircle className="w-4 h-4 text-rose-400 mt-0.5 shrink-0" />
                )}
                <div>
                  <div className="font-semibold">{testResult.message}</div>
                  {testResult.rabbitmq_version && (
                    <div className="mt-1 font-mono text-[11px] text-emerald-400/80">
                      RabbitMQ: {testResult.rabbitmq_version} | Erlang: {testResult.erlang_version}
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

          {saveError && (
            <div className="p-3 rounded-xl bg-rose-950/40 border border-rose-800/60 text-rose-300 text-xs flex items-center gap-2">
              <AlertCircle className="w-4 h-4 text-rose-400 shrink-0" />
              <span>{saveError}</span>
            </div>
          )}

          <div className="pt-2 flex items-center justify-between border-t border-slate-800">
            <button
              type="button"
              onClick={handleTest}
              disabled={isTesting}
              className="px-3.5 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 text-xs font-medium flex items-center gap-2 transition disabled:opacity-50"
            >
              {isTesting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Wifi className="w-3.5 h-3.5 text-orange-400" />}
              <span>Test Connection</span>
            </button>

            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={onClose}
                className="px-4 py-2 rounded-lg bg-transparent hover:bg-slate-800 text-slate-400 hover:text-slate-200 text-xs font-medium transition"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={isSaving}
                className="px-4 py-2 rounded-lg bg-orange-600 hover:bg-orange-500 text-white text-xs font-semibold shadow-lg shadow-orange-600/20 flex items-center gap-2 transition disabled:opacity-50"
              >
                {isSaving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Save className="w-3.5 h-3.5" />}
                <span>Save Settings</span>
              </button>
            </div>
          </div>
        </form>
      </div>
    </div>
  );
};
