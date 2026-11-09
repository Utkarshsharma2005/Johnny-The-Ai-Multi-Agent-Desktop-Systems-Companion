import React, { useState, useEffect } from 'react';
import { RequirementState } from '../hooks/useJohnnyApi';

interface RequirementCompilerPanelProps {
  requirementState: RequirementState | null;
  fetchRequirementState: () => Promise<void>;
  compileRequirements: (goal: string) => Promise<void>;
  lockRequirements: (answers: Record<string, string>) => Promise<void>;
  resetRequirements: () => Promise<void>;
}

export const RequirementCompilerPanel: React.FC<RequirementCompilerPanelProps> = ({
  requirementState,
  fetchRequirementState,
  compileRequirements,
  lockRequirements,
  resetRequirements,
}) => {
  const [goalText, setGoalText] = useState('');
  const [selectedAnswers, setSelectedAnswers] = useState<Record<string, string>>({});

  useEffect(() => {
    fetchRequirementState();
  }, [fetchRequirementState]);

  useEffect(() => {
    if (requirementState?.questions) {
      const defaults: Record<string, string> = {};
      requirementState.questions.forEach((q) => {
        defaults[q.id] = q.default_option;
      });
      setSelectedAnswers(defaults);
    }
  }, [requirementState]);

  const handleCompile = (e: React.FormEvent) => {
    e.preventDefault();
    if (!goalText.trim()) return;
    compileRequirements(goalText.trim());
  };

  const handleLock = () => {
    lockRequirements(selectedAnswers);
  };

  const isLocked = requirementState?.status === 'LOCKED';
  const isQuestionnaireReady = requirementState?.status === 'QUESTIONNAIRE_READY';

  return (
    <div className="p-4 space-y-6 text-slate-100 bg-slate-900/60 rounded-xl border border-slate-800 backdrop-blur-md">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-slate-800 pb-3">
        <div>
          <div className="flex items-center gap-2.5">
            <h2 className="text-xl font-bold tracking-tight text-white">Requirement Compiler</h2>
            <span
              className={`px-3 py-0.5 text-xs font-semibold rounded-full border ${
                isLocked
                  ? 'bg-emerald-950/40 text-emerald-400 border-emerald-800'
                  : isQuestionnaireReady
                  ? 'bg-indigo-950/40 text-indigo-300 border-indigo-800'
                  : 'bg-slate-800 text-slate-400 border-slate-700'
              }`}
            >
              {requirementState?.status || 'UNCOMPILED'}
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Consolidated requirement compilation & locking engine before starting complex tasks.
          </p>
        </div>

        {requirementState?.status !== 'UNCOMPILED' && (
          <button
            onClick={resetRequirements}
            className="px-3 py-1.5 text-xs font-medium bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg border border-slate-700 transition"
          >
            🔄 Reset
          </button>
        )}
      </div>

      {/* Goal Compile Input Form */}
      <form onSubmit={handleCompile} className="space-y-3">
        <label className="block text-xs font-medium text-slate-300">
          Target Task Goal Description
        </label>
        <div className="flex gap-2">
          <input
            type="text"
            placeholder="e.g. Build authentication with SQLite database..."
            value={goalText}
            onChange={(e) => setGoalText(e.target.value)}
            disabled={isLocked}
            className="flex-1 bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-indigo-500 transition"
          />
          <button
            type="submit"
            disabled={isLocked || !goalText.trim()}
            className="px-4 py-2 text-xs font-semibold bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl disabled:opacity-40 transition shadow-sm"
          >
            ⚡ Inspect & Compile
          </button>
        </div>
      </form>

      {/* Auto-detected Environment Requirements */}
      {requirementState?.known_requirements && Object.keys(requirementState.known_requirements).length > 0 && (
        <div className="bg-slate-950/80 rounded-xl p-3 border border-slate-800 space-y-2">
          <span className="text-xs font-bold text-slate-300 uppercase tracking-wider">
            Auto-Detected Workspace Environment
          </span>
          <div className="grid grid-cols-2 gap-2 text-xs">
            {Object.entries(requirementState.known_requirements).map(([key, val]) => (
              <div key={key} className="flex justify-between bg-slate-900/60 p-2 rounded-lg border border-slate-850">
                <span className="text-slate-400 capitalize">{key.replace(/_/g, ' ')}:</span>
                <span className="font-mono font-medium text-indigo-300">{String(val)}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Questionnaire Form */}
      {isQuestionnaireReady && requirementState?.questions && (
        <div className="space-y-4 bg-slate-950/60 p-4 rounded-xl border border-slate-800">
          <h3 className="text-xs font-bold text-slate-200 uppercase tracking-wider">
            Consolidated Questionnaire ({requirementState.questions.length} Decision Items)
          </h3>

          <div className="space-y-4">
            {requirementState.questions.map((q) => (
              <div key={q.id} className="space-y-2 bg-slate-900 p-3 rounded-lg border border-slate-800">
                <div className="font-semibold text-sm text-white">{q.question}</div>
                <div className="text-xs text-slate-400">{q.description}</div>

                <div className="flex flex-wrap gap-2 pt-1">
                  {q.options.map((opt) => {
                    const isSelected = (selectedAnswers[q.id] || q.default_option) === opt;
                    return (
                      <button
                        key={opt}
                        type="button"
                        onClick={() => setSelectedAnswers((prev) => ({ ...prev, [q.id]: opt }))}
                        className={`px-3 py-1.5 rounded-lg text-xs font-medium transition border ${
                          isSelected
                            ? 'bg-indigo-600 text-white border-indigo-500 shadow-sm'
                            : 'bg-slate-800 text-slate-300 border-slate-700 hover:bg-slate-750'
                        }`}
                      >
                        {opt}
                      </button>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>

          <button
            onClick={handleLock}
            className="w-full py-2.5 text-xs font-bold bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl transition shadow-md shadow-emerald-900/30"
          >
            🔒 Lock Requirements & Begin Autonomous Execution
          </button>
        </div>
      )}

      {/* Locked Specification Display */}
      {isLocked && requirementState?.locked_requirements && (
        <div className="space-y-3 bg-emerald-950/20 p-4 rounded-xl border border-emerald-800/60">
          <div className="flex items-center justify-between text-xs font-bold text-emerald-300">
            <span>🔒 Locked Requirement Specification</span>
            <span className="text-[10px] bg-emerald-900/60 text-emerald-200 px-2 py-0.5 rounded-full border border-emerald-700">LOCKED</span>
          </div>

          <div className="space-y-1.5 font-mono text-xs text-slate-200">
            {Object.entries(requirementState.locked_requirements).map(([key, val]) => (
              <div key={key} className="flex justify-between border-b border-emerald-900/40 pb-1">
                <span className="text-slate-400">{key}:</span>
                <span className="text-emerald-300 font-semibold">{String(val)}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
