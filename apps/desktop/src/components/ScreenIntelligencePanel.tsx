import React, { useEffect } from 'react';
import { ScreenState } from '../hooks/useJohnnyApi';

interface ScreenIntelligencePanelProps {
  screenState: ScreenState | null;
  fetchScreenState: () => Promise<void>;
  setScreenMode: (mode: string) => Promise<void>;
  triggerScreenCapture: (forceEscalate?: boolean, promptContext?: string) => Promise<void>;
  toggleScreenPause: () => Promise<void>;
}

export const ScreenIntelligencePanel: React.FC<ScreenIntelligencePanelProps> = ({
  screenState,
  fetchScreenState,
  setScreenMode,
  triggerScreenCapture,
  toggleScreenPause,
}) => {
  useEffect(() => {
    fetchScreenState();
    const timer = setInterval(() => {
      fetchScreenState();
    }, 10000);
    return () => clearInterval(timer);
  }, [fetchScreenState]);

  const isPaused = screenState?.status === 'PAUSED' || screenState?.mode === 'PAUSED';
  const currentMode = screenState?.mode || 'AMBIENT';
  const escalationLevel = screenState?.last_escalation_level ?? 0;

  const levelLabels = [
    { level: 0, label: 'L0: Capture', desc: 'Frame Capture' },
    { level: 1, label: 'L1: Change Detection', desc: 'Frame Diffing' },
    { level: 2, label: 'L2: Local Layout', desc: 'Metadata & Hashes' },
    { level: 3, label: 'L3: Vision Model', desc: 'MiniMax M3 LLM' },
  ];

  return (
    <div className="p-4 space-y-6 text-slate-100 bg-slate-900/60 rounded-xl border border-slate-800 backdrop-blur-md">
      {/* Top Header & Privacy Toggle */}
      <div className="flex items-center justify-between border-b border-slate-800 pb-4">
        <div>
          <div className="flex items-center gap-3">
            <h2 className="text-xl font-bold tracking-tight text-white">Screen Intelligence</h2>
            <span
              className={`px-3 py-0.5 text-xs font-semibold rounded-full border ${
                isPaused
                  ? 'bg-amber-950/40 text-amber-400 border-amber-800'
                  : 'bg-emerald-950/40 text-emerald-400 border-emerald-800'
              }`}
            >
              {isPaused ? '⏸️ PAUSED' : '👁️ OBSERVING'}
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Continuous 4-tier visual escalation monitoring (Low cost, high privacy).
          </p>
        </div>

        <button
          onClick={toggleScreenPause}
          className={`px-4 py-2 text-sm font-semibold rounded-lg transition-all ${
            isPaused
              ? 'bg-emerald-600 hover:bg-emerald-500 text-white shadow-lg shadow-emerald-900/40'
              : 'bg-amber-600 hover:bg-amber-500 text-white shadow-lg shadow-amber-900/40'
          }`}
        >
          {isPaused ? '▶️ Resume Intelligence' : '⏸️ Pause Observation'}
        </button>
      </div>

      {/* Observation Mode Selector */}
      <div>
        <label className="block text-xs font-medium text-slate-400 uppercase tracking-wider mb-2">
          Observation Mode
        </label>
        <div className="grid grid-cols-3 gap-3">
          {[
            { id: 'AMBIENT', name: 'Ambient', desc: 'Passive monitoring (5s interval)' },
            { id: 'ATTENTIVE', name: 'Attentive', desc: 'Active monitoring (1.5s interval)' },
            { id: 'TASK', name: 'Task', desc: 'Focused task focus (1.0s interval)' },
          ].map((modeItem) => {
            const isActive = currentMode === modeItem.id && !isPaused;
            return (
              <button
                key={modeItem.id}
                onClick={() => setScreenMode(modeItem.id)}
                disabled={isPaused}
                className={`p-3 rounded-xl border text-left transition-all ${
                  isActive
                    ? 'bg-indigo-900/40 border-indigo-500 text-white ring-2 ring-indigo-500/30'
                    : 'bg-slate-800/40 border-slate-800 text-slate-400 hover:border-slate-700 hover:text-slate-200'
                } ${isPaused ? 'opacity-50 cursor-not-allowed' : ''}`}
              >
                <div className="font-semibold text-sm">{modeItem.name}</div>
                <div className="text-xs text-slate-400 mt-1">{modeItem.desc}</div>
              </button>
            );
          })}
        </div>
      </div>

      {/* Escalation Level Stepper */}
      <div>
        <label className="block text-xs font-medium text-slate-400 uppercase tracking-wider mb-2">
          4-Tier Escalation Pipeline Status
        </label>
        <div className="grid grid-cols-4 gap-2">
          {levelLabels.map((lvl) => {
            const isReached = escalationLevel >= lvl.level;
            const isCurrent = escalationLevel === lvl.level;
            return (
              <div
                key={lvl.level}
                className={`p-3 rounded-lg border text-center transition-all ${
                  isCurrent
                    ? 'bg-cyan-950/60 border-cyan-400 text-cyan-200 shadow-md ring-1 ring-cyan-500/50'
                    : isReached
                    ? 'bg-slate-800/60 border-slate-700 text-slate-300'
                    : 'bg-slate-900/40 border-slate-850 text-slate-600'
                }`}
              >
                <div className="text-xs font-bold">{lvl.label}</div>
                <div className="text-[10px] text-slate-400 mt-0.5">{lvl.desc}</div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Current Screen Summary Card */}
      <div className="bg-slate-950/80 rounded-xl p-4 border border-slate-800 space-y-3">
        <div className="flex items-center justify-between text-xs text-slate-400 border-b border-slate-800/60 pb-2">
          <span>Active Screen Context Summary</span>
          <div className="flex gap-4">
            <span>Diff Score: <strong className="text-indigo-400">{(screenState?.last_diff_score ?? 0).toFixed(4)}</strong></span>
            <span>Escalations: <strong className="text-cyan-400">{screenState?.total_escalations ?? 0}</strong></span>
          </div>
        </div>

        <p className="text-sm text-slate-200 leading-relaxed font-mono whitespace-pre-wrap">
          {screenState?.screen_summary || 'No screen summary recorded.'}
        </p>

        <div className="flex items-center justify-between pt-2">
          <button
            onClick={() => triggerScreenCapture(false)}
            disabled={isPaused}
            className="px-3 py-1.5 text-xs font-medium bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-md border border-slate-700 transition"
          >
            📸 Capture & Evaluate
          </button>

          <button
            onClick={() => triggerScreenCapture(true, 'User explicit visual check')}
            disabled={isPaused}
            className="px-3 py-1.5 text-xs font-semibold bg-indigo-600 hover:bg-indigo-500 text-white rounded-md transition shadow-sm"
          >
            🚀 Force Vision Escalation (MiniMax M3)
          </button>
        </div>
      </div>
    </div>
  );
};
