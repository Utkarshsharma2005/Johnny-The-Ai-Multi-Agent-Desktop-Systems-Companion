import React, { useState, useEffect } from 'react';
import { Globe, ArrowRight, ShieldCheck, Camera, MousePointer, Type, RefreshCw } from 'lucide-react';
import { BrowserStatusState } from '../hooks/useJohnnyApi';

interface BrowserPanelProps {
  browserStatus: BrowserStatusState | null;
  fetchBrowserStatus: () => Promise<any>;
  navigateBrowser: (url: string) => Promise<any>;
  executeBrowserAction: (action: string, selector?: string, text?: string) => Promise<any>;
}

export const BrowserPanel: React.FC<BrowserPanelProps> = ({
  browserStatus,
  fetchBrowserStatus,
  navigateBrowser,
  executeBrowserAction
}) => {
  const [urlInput, setUrlInput] = useState('');
  const [selectorInput, setSelectorInput] = useState('');
  const [textInput, setTextInput] = useState('');
  const [actionLog, setActionLog] = useState<string[]>([]);
  const [isNavigating, setIsNavigating] = useState(false);
  const [navResult, setNavResult] = useState<any>(null);

  useEffect(() => {
    fetchBrowserStatus();
  }, [fetchBrowserStatus]);

  const handleNavigate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!urlInput.trim()) return;
    setIsNavigating(true);
    setNavResult(null);

    const targetUrl = urlInput.startsWith('http') ? urlInput : `https://${urlInput}`;
    const result = await navigateBrowser(targetUrl);
    setNavResult(result);
    setIsNavigating(false);

    if (result.success) {
      setActionLog((prev) => [`[NAVIGATE] Success -> ${targetUrl}`, ...prev.slice(0, 9)]);
    } else {
      setActionLog((prev) => [`[NAVIGATE] Error -> ${result.error || 'Blocked'}`, ...prev.slice(0, 9)]);
    }
  };

  const handleAction = async (actionType: string) => {
    const result = await executeBrowserAction(actionType, selectorInput, textInput);
    if (result.success) {
      setActionLog((prev) => [`[${actionType.toUpperCase()}] ${selectorInput || ''} ${textInput || ''}`, ...prev.slice(0, 9)]);
    } else {
      setActionLog((prev) => [`[${actionType.toUpperCase()}] Failed: ${result.error}`, ...prev.slice(0, 9)]);
    }
  };

  return (
    <div className="flex flex-col gap-4 text-slate-200 text-sm">
      {/* Header & Status Indicator */}
      <div className="flex items-center justify-between border-b border-slate-800 pb-3">
        <div className="flex items-center gap-2">
          <Globe className="h-5 w-5 text-sky-400" />
          <h3 className="font-semibold text-slate-100">Browser Automation (V0.9)</h3>
        </div>
        <div className="flex items-center gap-2">
          <span className="flex items-center gap-1 rounded-full bg-emerald-500/10 px-2 py-0.5 text-xs text-emerald-400 border border-emerald-500/20">
            <ShieldCheck className="h-3 w-3" /> HTTP/HTTPS Sandbox
          </span>
          <button
            onClick={() => fetchBrowserStatus()}
            className="rounded p-1 hover:bg-slate-800 text-slate-400 hover:text-slate-200 transition-colors"
            title="Refresh Status"
          >
            <RefreshCw className="h-4 w-4" />
          </button>
        </div>
      </div>

      {/* URL Navigation Input */}
      <form onSubmit={handleNavigate} className="flex gap-2">
        <div className="relative flex-1">
          <input
            type="text"
            value={urlInput}
            onChange={(e) => setUrlInput(e.target.value)}
            placeholder="Enter URL (e.g. https://example.com)..."
            className="w-full rounded-md bg-slate-900 border border-slate-700 px-3 py-1.5 text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-sky-500"
          />
        </div>
        <button
          type="submit"
          disabled={isNavigating}
          className="flex items-center gap-1.5 rounded-md bg-sky-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-sky-500 disabled:opacity-50 transition-colors"
        >
          {isNavigating ? <RefreshCw className="h-3.5 w-3.5 animate-spin" /> : <ArrowRight className="h-3.5 w-3.5" />}
          Navigate
        </button>
      </form>

      {/* Active Page Card */}
      <div className="rounded-lg bg-slate-900/60 border border-slate-800 p-3 flex flex-col gap-2">
        <div className="flex items-center justify-between text-xs text-slate-400">
          <span>Active URL: <strong className="text-sky-300">{browserStatus?.active_url || 'None'}</strong></span>
          <span>Title: <strong className="text-slate-200">{browserStatus?.active_title || 'Blank Page'}</strong></span>
        </div>

        {navResult && (
          <div className="rounded bg-slate-950 p-2 text-xs font-mono border border-slate-800 text-slate-300">
            <div className="text-emerald-400 font-bold mb-1">Page Title: {navResult.title}</div>
            <div className="text-slate-400 text-[11px] max-h-24 overflow-y-auto">
              {navResult.content_snippet || 'No text content available.'}
            </div>
          </div>
        )}
      </div>

      {/* Interactive Element Actions */}
      <div className="flex flex-col gap-2 rounded-lg bg-slate-900/40 border border-slate-800 p-3">
        <span className="text-xs font-semibold text-slate-300">Element Actions</span>
        <div className="grid grid-cols-2 gap-2">
          <input
            type="text"
            value={selectorInput}
            onChange={(e) => setSelectorInput(e.target.value)}
            placeholder="CSS selector (e.g. #submit)..."
            className="rounded bg-slate-900 border border-slate-700 px-2 py-1 text-xs text-slate-100 placeholder-slate-500"
          />
          <input
            type="text"
            value={textInput}
            onChange={(e) => setTextInput(e.target.value)}
            placeholder="Text to type..."
            className="rounded bg-slate-900 border border-slate-700 px-2 py-1 text-xs text-slate-100 placeholder-slate-500"
          />
        </div>

        <div className="flex items-center gap-2 pt-1">
          <button
            onClick={() => handleAction('click')}
            className="flex flex-1 items-center justify-center gap-1 rounded bg-slate-800 py-1.5 text-xs hover:bg-slate-700 transition-colors"
          >
            <MousePointer className="h-3.5 w-3.5 text-amber-400" /> Click
          </button>
          <button
            onClick={() => handleAction('type')}
            className="flex flex-1 items-center justify-center gap-1 rounded bg-slate-800 py-1.5 text-xs hover:bg-slate-700 transition-colors"
          >
            <Type className="h-3.5 w-3.5 text-indigo-400" /> Type Text
          </button>
          <button
            onClick={() => handleAction('screenshot')}
            className="flex flex-1 items-center justify-center gap-1 rounded bg-slate-800 py-1.5 text-xs hover:bg-slate-700 transition-colors"
          >
            <Camera className="h-3.5 w-3.5 text-emerald-400" /> Screenshot
          </button>
        </div>
      </div>

      {/* Action Logs */}
      {actionLog.length > 0 && (
        <div className="rounded bg-slate-950 p-2 border border-slate-800 text-[11px] font-mono text-slate-400">
          <div className="text-slate-500 font-semibold border-b border-slate-800 pb-1 mb-1">Browser Action History</div>
          {actionLog.map((log, i) => (
            <div key={i} className="truncate">{log}</div>
          ))}
        </div>
      )}
    </div>
  );
};
