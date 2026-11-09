import React, { useState, useEffect } from 'react';
import { ToolMetadata, ToolExecutionResult } from '../hooks/useJohnnyApi';

interface ToolsPanelProps {
  toolsList: ToolMetadata[];
  fetchTools: () => Promise<void>;
  executeTool: (toolName: string, args: Record<string, any>) => Promise<ToolExecutionResult>;
  lastToolResult: ToolExecutionResult | null;
}

export const ToolsPanel: React.FC<ToolsPanelProps> = ({
  toolsList,
  fetchTools,
  executeTool,
  lastToolResult,
}) => {
  const [selectedTool, setSelectedTool] = useState<string>('');
  const [argsJson, setArgsJson] = useState<string>('{}');
  const [isExecuting, setIsExecuting] = useState<boolean>(false);

  useEffect(() => {
    fetchTools();
  }, [fetchTools]);

  useEffect(() => {
    if (toolsList.length > 0 && !selectedTool) {
      setSelectedTool(toolsList[0].name);
      setArgsJson(JSON.stringify(getDefaultArgs(toolsList[0]), null, 2));
    }
  }, [toolsList, selectedTool]);

  const getDefaultArgs = (tool: ToolMetadata): Record<string, any> => {
    if (tool.name === 'read_file') return { file_path: 'README.md' };
    if (tool.name === 'list_dir') return { dir_path: '.' };
    if (tool.name === 'run_terminal_command') return { command: 'git status' };
    if (tool.name === 'write_file') return { file_path: 'sample.txt', content: 'Hello Johnny!' };
    if (tool.name === 'delete_file') return { file_path: 'sample.txt' };
    if (tool.name === 'git_commit') return { message: 'test commit' };
    if (tool.name === 'docker_logs') return { container_id: 'app', tail: 20 };
    return {};
  };

  const handleToolSelect = (name: string) => {
    setSelectedTool(name);
    const target = toolsList.find((t) => t.name === name);
    if (target) {
      setArgsJson(JSON.stringify(getDefaultArgs(target), null, 2));
    }
  };

  const handleRunTool = async () => {
    if (!selectedTool) return;
    setIsExecuting(true);
    try {
      let parsedArgs = {};
      try {
        parsedArgs = JSON.parse(argsJson);
      } catch (e) {
        alert('Invalid JSON in arguments field');
        setIsExecuting(false);
        return;
      }
      await executeTool(selectedTool, parsedArgs);
    } finally {
      setIsExecuting(false);
    }
  };

  const getSecurityBadge = (level: number) => {
    switch (level) {
      case 0:
        return <span className="bg-emerald-950/50 text-emerald-400 border border-emerald-800 px-2 py-0.5 rounded-full text-[10px]">Level 0: Safe Read</span>;
      case 1:
        return <span className="bg-indigo-950/50 text-indigo-300 border border-indigo-800 px-2 py-0.5 rounded-full text-[10px]">Level 1: Low Risk</span>;
      case 2:
        return <span className="bg-amber-950/50 text-amber-400 border border-amber-800 px-2 py-0.5 rounded-full text-[10px]">Level 2: Destructive</span>;
      case 3:
        return <span className="bg-rose-950/50 text-rose-400 border border-rose-800 px-2 py-0.5 rounded-full text-[10px]">Level 3: Dangerous System</span>;
      default:
        return <span className="bg-slate-800 text-slate-400 px-2 py-0.5 rounded-full text-[10px]">Level {level}</span>;
    }
  };

  const targetToolObj = toolsList.find((t) => t.name === selectedTool);

  return (
    <div className="p-4 space-y-6 text-slate-100 bg-slate-900/60 rounded-xl border border-slate-800 backdrop-blur-md">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-slate-800 pb-3">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-xl font-bold tracking-tight text-white">Tool Sandbox & Security Engine</h2>
            <span className="px-2.5 py-0.5 text-xs font-semibold rounded-full bg-indigo-950/50 text-indigo-300 border border-indigo-800">
              {toolsList.length} Tools Registered
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Controlled workspace tool execution with 4-tier security sandboxing.
          </p>
        </div>
      </div>

      {/* Tools Selector List */}
      <div>
        <label className="block text-xs font-medium text-slate-400 uppercase tracking-wider mb-2">
          Registered Controlled Tools
        </label>
        <div className="grid grid-cols-2 gap-2 max-h-48 overflow-y-auto pr-1">
          {toolsList.map((tool) => {
            const isSelected = tool.name === selectedTool;
            return (
              <button
                key={tool.name}
                onClick={() => handleToolSelect(tool.name)}
                className={`p-2.5 rounded-xl border text-left transition ${
                  isSelected
                    ? 'bg-indigo-900/40 border-indigo-500 text-white ring-1 ring-indigo-500/40'
                    : 'bg-slate-950/60 border-slate-850 text-slate-300 hover:border-slate-700'
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="font-bold text-xs font-mono">{tool.name}</span>
                  {getSecurityBadge(tool.security_level)}
                </div>
                <p className="text-[11px] text-slate-400 mt-1 line-clamp-1">{tool.description}</p>
              </button>
            );
          })}
        </div>
      </div>

      {/* Interactive Tool Execution Playground */}
      {targetToolObj && (
        <div className="space-y-3 bg-slate-950/80 p-4 rounded-xl border border-slate-800">
          <div className="flex items-center justify-between border-b border-slate-800 pb-2">
            <div className="flex items-center gap-2">
              <span className="text-sm font-bold text-indigo-300 font-mono">{targetToolObj.name}</span>
              {getSecurityBadge(targetToolObj.security_level)}
            </div>
            <span className="text-xs text-slate-400">{targetToolObj.description}</span>
          </div>

          <div className="space-y-2">
            <label className="block text-xs font-medium text-slate-300">Tool Arguments (JSON)</label>
            <textarea
              rows={4}
              value={argsJson}
              onChange={(e) => setArgsJson(e.target.value)}
              className="w-full bg-slate-900 border border-slate-800 rounded-xl p-3 font-mono text-xs text-slate-200 focus:outline-none focus:border-indigo-500 transition"
            />
          </div>

          {targetToolObj.security_level >= 2 && (
            <p className="text-xs text-amber-300 bg-amber-950/30 p-2.5 rounded-lg border border-amber-900/50">
              This action will wait for your approval in the agent activity feed before it runs.
            </p>
          )}

          <button
            onClick={handleRunTool}
            disabled={isExecuting}
            className="w-full py-2 text-xs font-bold bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl transition shadow-md disabled:opacity-40"
          >
            {isExecuting ? 'Executing Tool...' : `▶️ Execute ${targetToolObj.name}`}
          </button>
        </div>
      )}

      {/* Execution Result Feed */}
      {lastToolResult && (
        <div
          className={`p-4 rounded-xl border space-y-2 font-mono text-xs ${
            lastToolResult.success
              ? 'bg-slate-950 border-emerald-800/80 text-slate-200'
              : 'bg-rose-950/30 border-rose-800/80 text-rose-200'
          }`}
        >
          <div className="flex items-center justify-between border-b border-slate-800 pb-2">
            <span className="font-bold">
              {lastToolResult.success ? '✅ Execution Succeeded' : '❌ Permission / Execution Failed'}
            </span>
            <span className="text-slate-400">⚡ {lastToolResult.latency_ms} ms</span>
          </div>

          {lastToolResult.error && (
            <div className="text-rose-300 font-sans">{lastToolResult.error}</div>
          )}

          {lastToolResult.approval_required && (
            <div className="text-amber-300 font-sans">Approval requested. Review the exact action in the Agent Activity panel.</div>
          )}

          {lastToolResult.result && (
            <pre className="overflow-x-auto p-2 bg-slate-900 rounded-lg text-[11px] text-slate-300 max-h-40">
              {JSON.stringify(lastToolResult.result, null, 2)}
            </pre>
          )}
        </div>
      )}
    </div>
  );
};
