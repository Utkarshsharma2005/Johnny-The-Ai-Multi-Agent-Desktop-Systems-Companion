import React, { useState, useEffect } from 'react';
import { TaskState } from '../hooks/useJohnnyApi';

interface TaskExecutionPanelProps {
  tasksList: TaskState[];
  activeTask: TaskState | null;
  fetchTasks: () => Promise<void>;
  createTask: (goal: string) => Promise<TaskState | null>;
  executeTask: (taskId: string) => Promise<TaskState | null>;
}

export const TaskExecutionPanel: React.FC<TaskExecutionPanelProps> = ({
  tasksList,
  activeTask,
  fetchTasks,
  createTask,
  executeTask,
}) => {
  const [goalPrompt, setGoalPrompt] = useState('');
  const [isCreating, setIsCreating] = useState(false);
  const [isExecuting, setIsExecuting] = useState(false);

  useEffect(() => {
    fetchTasks();
  }, [fetchTasks]);

  const handleCreateTask = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!goalPrompt.trim()) return;
    setIsCreating(true);
    try {
      await createTask(goalPrompt.trim());
      setGoalPrompt('');
    } finally {
      setIsCreating(false);
    }
  };

  const handleExecuteTask = async () => {
    if (!activeTask) return;
    setIsExecuting(true);
    try {
      await executeTask(activeTask.id);
    } finally {
      setIsExecuting(false);
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'COMPLETED':
        return <span className="bg-emerald-950/50 text-emerald-400 border border-emerald-800 px-2.5 py-0.5 rounded-full text-xs font-semibold">✅ COMPLETED</span>;
      case 'EXECUTION':
      case 'VERIFYING':
        return <span className="bg-indigo-950/50 text-indigo-300 border border-indigo-800 px-2.5 py-0.5 rounded-full text-xs font-semibold animate-pulse">⚡ {status}</span>;
      case 'RECOVERING':
        return <span className="bg-amber-950/50 text-amber-300 border border-amber-800 px-2.5 py-0.5 rounded-full text-xs font-semibold animate-pulse">🛠️ RECOVERING</span>;
      case 'FAILED':
        return <span className="bg-rose-950/50 text-rose-400 border border-rose-800 px-2.5 py-0.5 rounded-full text-xs font-semibold">❌ FAILED</span>;
      default:
        return <span className="bg-slate-800 text-slate-300 border border-slate-700 px-2.5 py-0.5 rounded-full text-xs font-semibold">{status}</span>;
    }
  };

  return (
    <div className="p-4 space-y-6 text-slate-100 bg-slate-900/60 rounded-xl border border-slate-800 backdrop-blur-md">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-slate-800 pb-3">
        <div>
          <h2 className="text-xl font-bold tracking-tight text-white">Autonomous Task Engine</h2>
          <p className="text-xs text-slate-400 mt-1">
            Multi-step task execution with closed-loop verification & recovery.
          </p>
        </div>
      </div>

      {/* Create Task Form */}
      <form onSubmit={handleCreateTask} className="space-y-2">
        <label className="block text-xs font-medium text-slate-300">Create New Autonomous Task</label>
        <div className="flex gap-2">
          <input
            type="text"
            placeholder="e.g. Build authentication endpoints and verify pytest suite..."
            value={goalPrompt}
            onChange={(e) => setGoalPrompt(e.target.value)}
            className="flex-1 bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-indigo-500 transition"
          />
          <button
            type="submit"
            disabled={isCreating || !goalPrompt.trim()}
            className="px-4 py-2 text-xs font-semibold bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl disabled:opacity-40 transition shadow-sm"
          >
            {isCreating ? 'Creating...' : '➕ Create Task'}
          </button>
        </div>
      </form>

      {/* Active Task Dashboard */}
      {activeTask && (
        <div className="space-y-4 bg-slate-950/80 p-4 rounded-xl border border-slate-800">
          <div className="flex items-center justify-between border-b border-slate-800 pb-3">
            <div>
              <div className="flex items-center gap-2">
                <span className="font-mono text-xs font-bold text-indigo-400">{activeTask.id}</span>
                {getStatusBadge(activeTask.status)}
              </div>
              <h3 className="text-sm font-semibold text-white mt-1">{activeTask.goal}</h3>
            </div>

            <button
              onClick={handleExecuteTask}
              disabled={isExecuting || activeTask.status === 'COMPLETED'}
              className="px-4 py-2 text-xs font-bold bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl transition shadow-md shadow-emerald-900/30 disabled:opacity-40"
            >
              {isExecuting ? 'Executing Loop...' : '▶️ Execute Task Loop'}
            </button>
          </div>

          {/* Steps Timeline */}
          <div className="space-y-2">
            <label className="block text-xs font-medium text-slate-400 uppercase tracking-wider">
              Decomposed Plan Execution Steps
            </label>
            <div className="space-y-2">
              {activeTask.steps.map((step) => (
                <div
                  key={step.step_number}
                  className="flex items-center justify-between p-3 rounded-lg bg-slate-900 border border-slate-800 text-xs"
                >
                  <div className="flex items-center gap-3">
                    <span className="font-mono font-bold text-slate-400">#{step.step_number}</span>
                    <span className="text-slate-200">{step.description}</span>
                    {step.tool_name && (
                      <span className="font-mono bg-slate-800 text-indigo-300 px-2 py-0.5 rounded text-[10px]">
                        🛠️ {step.tool_name}
                      </span>
                    )}
                  </div>
                  <span
                    className={`font-semibold text-[10px] px-2 py-0.5 rounded-full ${
                      step.status === 'COMPLETED'
                        ? 'bg-emerald-950 text-emerald-300'
                        : step.status === 'FAILED'
                        ? 'bg-rose-950 text-rose-300'
                        : step.status === 'RUNNING'
                        ? 'bg-indigo-950 text-indigo-300 animate-pulse'
                        : 'bg-slate-800 text-slate-400'
                    }`}
                  >
                    {step.status}
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* Execution Logs */}
          <div className="space-y-2">
            <label className="block text-xs font-medium text-slate-400 uppercase tracking-wider">
              Live Task Execution Logs
            </label>
            <pre className="overflow-x-auto p-3 bg-slate-900 rounded-xl font-mono text-[11px] text-slate-300 max-h-40">
              {activeTask.logs.join('\n') || 'No execution logs recorded.'}
            </pre>
          </div>
        </div>
      )}
    </div>
  );
};
