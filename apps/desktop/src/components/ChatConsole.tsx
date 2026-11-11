import React, { useState, useRef, useEffect } from 'react';
import {
  MessageSquare,
  Cpu,
  Activity,
  Settings as SettingsIcon,
  Send,
  Image as ImageIcon,
  Minimize2,
  CheckCircle2,
  Terminal,
  Zap,
  Eye,
  CheckSquare,
  Wrench,
  Globe,
  Database,
  GripHorizontal,
  RotateCcw,
  Maximize2,
  Minus,
  Square,
  X
} from 'lucide-react';
import {
  ChatMessage,
  TelemetryData,
  ScreenState,
  RequirementState,
  ToolMetadata,
  ToolExecutionResult,
  VerificationReport,
  TaskState,
  BrowserStatusState,
  MemoryItem
} from '../hooks/useJohnnyApi';
import { ScreenIntelligencePanel } from './ScreenIntelligencePanel';
import { RequirementCompilerPanel } from './RequirementCompilerPanel';
import { ToolsPanel } from './ToolsPanel';
import { VerificationPanel } from './VerificationPanel';
import { TaskExecutionPanel } from './TaskExecutionPanel';
import { BrowserPanel } from './BrowserPanel';
import { MemoryPanel } from './MemoryPanel';
import { MultiAgentPanel } from './MultiAgentPanel';
import { isWheelSoundEnabled, setWheelSoundEnabled } from '../engine/wheelSounds';

type TabId = 'chat' | 'browser' | 'memory' | 'screen' | 'reqs' | 'tools' | 'tasks' | 'verify' | 'models' | 'telemetry' | 'settings';

interface ChatConsoleProps {
  messages: ChatMessage[];
  onSendMessage: (prompt: string, imagePath?: string) => void;
  isProcessing: boolean;
  telemetry: TelemetryData | null;
  screenState?: ScreenState | null;
  fetchScreenState?: () => Promise<void>;
  setScreenMode?: (mode: string) => Promise<void>;
  triggerScreenCapture?: (forceEscalate?: boolean, promptContext?: string) => Promise<void>;
  toggleScreenPause?: () => Promise<void>;
  requirementState?: RequirementState | null;
  fetchRequirementState?: () => Promise<void>;
  compileRequirements?: (goal: string) => Promise<void>;
  lockRequirements?: (answers: Record<string, string>) => Promise<void>;
  resetRequirements?: () => Promise<void>;
  toolsList?: ToolMetadata[];
  fetchTools?: () => Promise<void>;
  executeTool?: (toolName: string, args: Record<string, any>, userApproved?: boolean) => Promise<ToolExecutionResult>;
  lastToolResult?: ToolExecutionResult | null;
  verificationReport?: VerificationReport | null;
  runVerification?: (checks?: string[]) => Promise<VerificationReport | null>;
  tasksList?: TaskState[];
  activeTask?: TaskState | null;
  fetchTasks?: () => Promise<void>;
  createTask?: (goal: string) => Promise<TaskState | null>;
  executeTask?: (taskId: string) => Promise<TaskState | null>;
  browserStatus?: BrowserStatusState | null;
  fetchBrowserStatus?: () => Promise<any>;
  navigateBrowser?: (url: string) => Promise<any>;
  executeBrowserAction?: (action: string, selector?: string, text?: string) => Promise<any>;
  memoryItems?: MemoryItem[];
  queryMemory?: (term?: string, tier?: string) => Promise<any>;
  recordMemory?: (tier: string, key: string, value: string, tags?: string[]) => Promise<boolean>;
  clearMemoryTier?: (tier: string) => Promise<boolean>;
  onStopGenerating?: () => void;
  onClose: () => void;
  defaultTab?: string;
  character?: string;
  onSelectCharacter?: (char: string) => void;
}

export const ChatConsole: React.FC<ChatConsoleProps> = ({
  messages,
  onSendMessage,
  isProcessing,
  telemetry,
  screenState,
  fetchScreenState,
  setScreenMode,
  triggerScreenCapture,
  toggleScreenPause,
  requirementState,
  fetchRequirementState,
  compileRequirements,
  lockRequirements,
  resetRequirements,
  toolsList,
  fetchTools,
  executeTool,
  lastToolResult,
  verificationReport,
  runVerification,
  tasksList,
  activeTask,
  fetchTasks,
  createTask,
  executeTask,
  browserStatus,
  fetchBrowserStatus,
  navigateBrowser,
  executeBrowserAction,
  memoryItems,
  queryMemory,
  recordMemory,
  clearMemoryTier,
  onStopGenerating,
  onClose,
  defaultTab,
  character = 'spongebob',
  onSelectCharacter,
}) => {
  const [activeTab, setActiveTab] = useState<TabId>((defaultTab as TabId) ?? 'chat');
  const [wheelSoundsEnabled, setWheelSoundsEnabled] = useState(isWheelSoundEnabled);

  // Sync when skill wheel changes the requested tab
  useEffect(() => {
    if (defaultTab) setActiveTab(defaultTab as TabId);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [defaultTab]);
  const [inputText, setInputText] = useState('');
  const [imagePath, setImagePath] = useState('');
  const [showImagePathInput, setShowImagePathInput] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement | null>(null);

  // ── Resize helpers ─────────────────────────────────────────────────────────
  // Clamps w/h so the console always stays inside the current viewport.
  // The pet dog (~140px) sits to the right, so we reserve 160px on that side.
  const clampDimensions = (w: number, h: number) => ({
    width:  Math.max(380, Math.min(window.innerWidth  - 160, w)),
    height: Math.max(400, Math.min(window.innerHeight -  20,  h)),
  });

  // Dimension state — initialised from localStorage but immediately clamped
  // to the actual viewport so stale saved values never overflow.
  const [dimensions, setDimensions] = useState<{ width: number; height: number }>(() => {
    const rawW = parseInt(localStorage.getItem('johnny_console_width')  ?? '560', 10);
    const rawH = parseInt(localStorage.getItem('johnny_console_height') ?? '640', 10);
    return clampDimensions(rawW, rawH);
  });
  const [isResizing, setIsResizing] = useState(false);
  const [isMaximized, setIsMaximized] = useState(false);
  const savedDimensionsRef = useRef<{ width: number; height: number } | null>(null);
  const resizeStartRef = useRef<{ x: number; y: number; w: number; h: number } | null>(null);

  const toggleMaximize = () => {
    if (isMaximized) {
      const restored = savedDimensionsRef.current ? clampDimensions(savedDimensionsRef.current.width, savedDimensionsRef.current.height) : clampDimensions(560, 640);
      setDimensions(restored);
      setIsMaximized(false);
    } else {
      savedDimensionsRef.current = { ...dimensions };
      const maxW = Math.max(480, window.innerWidth - 180);
      const maxH = Math.max(400, window.innerHeight - 30);
      setDimensions({ width: maxW, height: maxH });
      setIsMaximized(true);
    }
  };

  const resetDimensions = () => {
    setIsMaximized(false);
    const clamped = clampDimensions(560, 640);
    setDimensions(clamped);
    localStorage.setItem('johnny_console_width',  clamped.width.toString());
    localStorage.setItem('johnny_console_height', clamped.height.toString());
  };

  const startResizing = (e: React.MouseEvent, corner: 'top-left' | 'bottom-left' | 'bottom-right') => {
    e.preventDefault();
    e.stopPropagation();
    setIsResizing(true);
    resizeStartRef.current = { x: e.clientX, y: e.clientY, w: dimensions.width, h: dimensions.height };

    const handleMouseMove = (moveEvent: MouseEvent) => {
      if (!resizeStartRef.current) return;
      const dx = moveEvent.clientX - resizeStartRef.current.x;
      const dy = moveEvent.clientY - resizeStartRef.current.y;
      let newW = resizeStartRef.current.w;
      let newH = resizeStartRef.current.h;

      if (corner === 'bottom-left')       { newW -= dx; newH += dy; }
      else if (corner === 'top-left')     { newW -= dx; newH -= dy; }
      else if (corner === 'bottom-right') { newW += dx; newH += dy; }

      const clamped = clampDimensions(newW, newH);
      setDimensions(clamped);
      localStorage.setItem('johnny_console_width',  clamped.width.toString());
      localStorage.setItem('johnny_console_height', clamped.height.toString());
    };

    const handleMouseUp = () => {
      setIsResizing(false);
      resizeStartRef.current = null;
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup',   handleMouseUp);
    };

    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseup',   handleMouseUp);
  };

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputText.trim() && !imagePath.trim()) return;
    onSendMessage(inputText, imagePath.trim() ? imagePath.trim() : undefined);
    setInputText('');
    setImagePath('');
    setShowImagePathInput(false);
  };

  const tabBtn = (id: TabId, label: string, icon: React.ReactNode) => (
    <button
      onClick={() => setActiveTab(id)}
      className={`tab-btn${activeTab === id ? ' is-active' : ''}`}
    >
      {icon}
      {label}
    </button>
  );

  return (
    <div
      className="glass-panel"
      style={{
        position: 'relative',
        display: 'flex',
        flexDirection: 'column',
        width:  dimensions.width,
        height: dimensions.height,
        minWidth:  380,
        minHeight: 400,
        overflow: 'hidden',
        userSelect: isResizing ? 'none' : 'auto',
      }}
    >
      <div onMouseDown={(e) => startResizing(e, 'top-left')}     className="resize-handle top-left"    title="Resize" />
      <div onMouseDown={(e) => startResizing(e, 'bottom-left')}  className="resize-handle bottom-left"  title="Resize" />
      <div onMouseDown={(e) => startResizing(e, 'bottom-right')} className="resize-handle bottom-right" title="Resize" />

      {/* ── Header ── */}
      <div className="console-header" data-tauri-drag-region="true">
        <div className="console-header-logo">
          {character === 'spongebob' ? '🧽' : character === 'deadpool' ? '⚔️' : character === 'klee' ? '🍀' : '🐶'}
        </div>
        <div className="console-header-title" data-tauri-drag-region="true" style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <h2 style={{ fontSize: 13, fontWeight: 700, margin: 0 }}>Johnny Console</h2>
            {activeTask && (activeTask.status === 'EXECUTION' || activeTask.status === 'PLANNING' || activeTask.status === 'VERIFYING') && (
              <span style={{ fontSize: 9, padding: '1px 6px', borderRadius: 999, background: 'hsla(38, 92%, 56%, 0.2)', color: 'var(--j-amber)', border: '1px solid hsla(38, 92%, 56%, 0.4)', fontWeight: 600 }}>
                ⚡ Task Active
              </span>
            )}
            {isProcessing && (
              <span style={{ fontSize: 9, padding: '1px 6px', borderRadius: 999, background: 'hsla(270, 70%, 65%, 0.2)', color: 'var(--j-purple)', border: '1px solid hsla(270, 70%, 65%, 0.4)', fontWeight: 600 }}>
                Thinking…
              </span>
            )}
          </div>
          <p style={{ fontSize: 10, color: 'var(--j-text-dim)', margin: 0 }}>
            {character.toUpperCase()} · {dimensions.width}×{dimensions.height}px
          </p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          <button onClick={resetDimensions} className="icon-btn" title="Reset standard size (560×640)"><RotateCcw size={13} /></button>
          <button onClick={toggleMaximize} className="icon-btn" title={isMaximized ? "Restore window" : "Maximize window"}>
            {isMaximized ? <Minimize2 size={13} /> : <Maximize2 size={13} />}
          </button>
          <button onClick={onClose} className="icon-btn" title="Minimize / Hide to pet"><Minus size={13} /></button>
          <button onClick={onClose} className="icon-btn" title="Close" style={{ color: 'var(--j-rose)' }}><X size={14} /></button>
        </div>
      </div>

      {/* ── Tab Bar ── */}
      <div className="tab-bar no-scrollbar">
        {tabBtn('chat',     'Chat',      <MessageSquare size={13} />)}
        {tabBtn('browser',  'Browser',   <Globe         size={13} />)}
        {tabBtn('memory',   'Memory',    <Database      size={13} />)}
        {tabBtn('screen',   'Screen',    <Eye           size={13} />)}
        {tabBtn('reqs',     'Reqs',      <CheckSquare   size={13} />)}
        {tabBtn('tools',    'Tools',     <Wrench        size={13} />)}
        {tabBtn('tasks',    'Tasks',     <Terminal      size={13} />)}
        {tabBtn('verify',   'Verify',    <CheckCircle2  size={13} />)}
        {tabBtn('models',   'Models',    <Cpu           size={13} />)}
        {tabBtn('telemetry','Telemetry', <Activity      size={13} />)}
        {tabBtn('settings', 'Settings',  <SettingsIcon  size={13} />)}
      </div>

      {/* ── Tab Content ── */}
      <div style={{ flex: 1, overflowY: 'auto', padding: 14, minHeight: 0 }}>
        {/* Chat */}
        {activeTab === 'chat' && (
          <div className="chat-messages" style={{ padding: 0 }}>
            {messages.length === 0 && (
              <div style={{ margin: 'auto', textAlign: 'center', paddingTop: 48 }}>
                <div style={{ fontSize: 32, marginBottom: 8 }}>🐾</div>
                <p style={{ fontSize: 13, fontWeight: 700, color: 'var(--j-text)' }}>Ask Johnny anything</p>
                <p style={{ fontSize: 11, color: 'var(--j-text-dim)', marginTop: 4 }}>Powered by Llama 70B · Vision · DeepSeek R1</p>
              </div>
            )}
            {messages.map((msg) => (
              <div
                key={msg.id}
                style={{ display: 'flex', flexDirection: 'column', alignItems: msg.sender === 'user' ? 'flex-end' : 'flex-start' }}
              >
                <div className={msg.sender === 'user' ? 'msg msg-user' : 'msg msg-johnny'}>
                  <p style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
                    {msg.text || (msg.isStreaming ? '' : '')}
                    {msg.isStreaming && !msg.text && <span className="stream-cursor" />}
                    {msg.isStreaming && msg.text && <span className="stream-cursor" />}
                  </p>
                  {msg.modelUsed && (
                    <div style={{ marginTop: 6, paddingTop: 6, borderTop: '1px solid var(--j-border)', display: 'flex', justifyContent: 'space-between', fontSize: 10, fontFamily: 'var(--j-font-mono)', opacity: 0.7 }}>
                      <span>🤖 {msg.modelUsed}</span>
                      {msg.telemetry && <span>⚡ {msg.telemetry.total_ms}ms</span>}
                    </div>
                  )}
                </div>
                <span style={{ marginTop: 3, fontSize: 9, color: 'var(--j-text-faint)', padding: '0 4px' }}>{msg.timestamp}</span>
              </div>
            ))}
            <div ref={messagesEndRef} />
          </div>
        )}

        {activeTab === 'browser' && (
          <BrowserPanel
            browserStatus={browserStatus ?? null}
            fetchBrowserStatus={fetchBrowserStatus ?? (async () => null)}
            navigateBrowser={navigateBrowser ?? (async () => null)}
            executeBrowserAction={executeBrowserAction ?? (async () => null)}
          />
        )}

        {activeTab === 'memory' && (
          <MemoryPanel
            memoryItems={memoryItems ?? []}
            queryMemory={queryMemory ?? (async () => [])}
            recordMemory={recordMemory ?? (async () => false)}
            clearMemoryTier={clearMemoryTier ?? (async () => false)}
          />
        )}

        {activeTab === 'screen' && (
          <ScreenIntelligencePanel
            screenState={screenState ?? null}
            fetchScreenState={fetchScreenState ?? (async () => {})}
            setScreenMode={setScreenMode ?? (async () => {})}
            triggerScreenCapture={triggerScreenCapture ?? (async () => {})}
            toggleScreenPause={toggleScreenPause ?? (async () => {})}
          />
        )}

        {activeTab === 'reqs' && (
          <RequirementCompilerPanel
            requirementState={requirementState ?? null}
            fetchRequirementState={fetchRequirementState ?? (async () => {})}
            compileRequirements={compileRequirements ?? (async () => {})}
            lockRequirements={lockRequirements ?? (async () => {})}
            resetRequirements={resetRequirements ?? (async () => {})}
          />
        )}

        {activeTab === 'tools' && (
          <ToolsPanel
            toolsList={toolsList ?? []}
            fetchTools={fetchTools ?? (async () => {})}
            executeTool={executeTool ?? (async () => ({ success: false, tool_name: '', security_level: 0, latency_ms: 0 }))}
            lastToolResult={lastToolResult ?? null}
          />
        )}

        {activeTab === 'tasks' && (
          <TaskExecutionPanel
            tasksList={tasksList ?? []}
            activeTask={activeTask ?? null}
            fetchTasks={fetchTasks ?? (async () => {})}
            createTask={createTask ?? (async () => null)}
            executeTask={executeTask ?? (async () => null)}
          />
        )}

        {activeTab === 'verify' && (
          <VerificationPanel
            verificationReport={verificationReport ?? null}
            runVerification={runVerification ?? (async () => null)}
          />
        )}

        {activeTab === 'models' && (
          <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
            <MultiAgentPanel />
          </div>
        )}

        {activeTab === 'telemetry' && (
          <div className="space-y-3">
            <h3 className="text-[11px] font-bold text-slate-400 uppercase tracking-widest mb-3">Request Latency Breakdown</h3>
            {telemetry ? (
              <div className="space-y-2">
                {[
                  { label: 'Model Router Latency', value: telemetry.routing_ms, total: telemetry.total_ms, color: 'indigo' },
                  { label: 'Downstream Model Latency', value: telemetry.model_ms, total: telemetry.total_ms, color: 'purple' },
                ].map((t) => (
                  <div key={t.label} className="glass-card p-3 rounded-xl border border-slate-800">
                    <div className="flex justify-between text-xs mb-1.5">
                      <span className="text-slate-400">{t.label}</span>
                      <span className={`font-mono text-${t.color}-400 font-semibold`}>{t.value} ms</span>
                    </div>
                    <div className="h-1.5 w-full bg-slate-800 rounded-full overflow-hidden">
                      <div className={`h-full bg-${t.color}-500 transition-all`} style={{ width: `${Math.min(100, (t.value / (t.total || 1)) * 100)}%` }} />
                    </div>
                  </div>
                ))}
                <div className="glass-card p-3 rounded-xl border border-slate-800">
                  <div className="flex justify-between text-xs">
                    <span className="text-slate-400">Total Request Latency</span>
                    <span className="font-mono text-emerald-400 font-bold">{telemetry.total_ms} ms</span>
                  </div>
                </div>
              </div>
            ) : (
              <p className="text-xs text-slate-400">No telemetry yet. Send a message to inspect timing metrics.</p>
            )}
          </div>
        )}

        {activeTab === 'settings' && (
          <div className="space-y-4">
            <div>
              <h3 className="text-[11px] font-bold text-slate-400 uppercase tracking-widest mb-2">Desktop Pet Character</h3>
              <div className="grid grid-cols-2 gap-2">
                {[
                  { id: 'spongebob', name: 'SpongeBob', role: 'Playful & High Energy' },
                  { id: 'deadpool',  name: 'Deadpool',  role: 'Snarky Code Partner' },
                  { id: 'klee',      name: 'Klee',      role: 'Curious Explorer' },
                  { id: 'albedo',    name: 'Albedo',    role: 'Calm Alchemist' },
                ].map((c) => (
                  <button
                    key={c.id}
                    type="button"
                    onClick={() => onSelectCharacter?.(c.id)}
                    className={`flex items-center gap-2 p-2 rounded-xl text-left transition-all ${
                      character === c.id
                        ? 'bg-indigo-600/30 border border-indigo-500/70 shadow-lg shadow-indigo-500/20'
                        : 'bg-slate-900/60 border border-slate-800 hover:border-slate-700'
                    }`}
                  >
                    <img
                      src={`/assets/${c.id}/walk1.png`}
                      alt={c.name}
                      className="w-10 h-10 object-contain"
                    />
                    <div>
                      <div className="text-xs font-bold text-slate-100">{c.name}</div>
                      <div className="text-[10px] text-slate-400">{c.role}</div>
                    </div>
                  </button>
                ))}
              </div>
            </div>

            <div className="glass-card flex items-center justify-between gap-3 p-3 rounded-xl border border-slate-800">
              <div>
                <h3 className="text-[11px] font-bold text-slate-200">Skill wheel sounds</h3>
                <p className="text-[10px] text-slate-400 mt-1">Soft cues for opening, selecting, and hovering over wheel actions.</p>
              </div>
              <button
                type="button"
                role="switch"
                aria-checked={wheelSoundsEnabled}
                onClick={() => {
                  const next = !wheelSoundsEnabled;
                  setWheelSoundsEnabled(next);
                  setWheelSoundEnabled(next);
                }}
                className={`shrink-0 rounded-full px-3 py-1 text-[10px] font-semibold border transition-colors ${wheelSoundsEnabled ? 'bg-indigo-500/20 border-indigo-400/50 text-indigo-200' : 'bg-slate-900 border-slate-700 text-slate-400'}`}
              >
                {wheelSoundsEnabled ? 'On' : 'Off'}
              </button>
            </div>

            <div>
              <h3 className="text-[11px] font-bold text-slate-400 uppercase tracking-widest mb-2">System Diagnostics</h3>
              <div className="glass-card p-3 rounded-xl border border-slate-800 space-y-2 text-xs">
                {[
                  { label: 'Backend Endpoint',     value: 'http://127.0.0.1:8000',   cls: 'font-mono text-indigo-400' },
                  { label: 'Desktop Framework',    value: 'Tauri 2 (Rust / Linux)',  cls: 'font-mono text-slate-300' },
                  { label: 'Security Sandbox',     value: 'Level 0 Safe Read',        cls: 'text-emerald-400 font-semibold' },
                  { label: 'Physics Engine',       value: '60 FPS Shimeji Physics',  cls: 'text-sky-400 font-mono' },
                  { label: 'Agent Release Version',value: 'V1.1.0 (Production)',      cls: 'text-amber-400 font-bold' },
                ].map((s) => (
                  <div key={s.label} className="flex justify-between items-center">
                    <span className="text-slate-300">{s.label}</span>
                    <span className={s.cls}>{s.value}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* ── Chat Input Footer ── */}
      {activeTab === 'chat' && (
        <form onSubmit={handleSubmit} className="chat-input-row" style={{ flexDirection: 'column', gap: 8 }}>
          {showImagePathInput && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, background: 'var(--j-bg-elevated)', padding: '6px 12px', borderRadius: 'var(--j-r-md)', border: '1px solid var(--j-border)' }}>
              <ImageIcon size={13} style={{ color: 'var(--j-purple)', flexShrink: 0 }} />
              <input
                type="text"
                placeholder="Local image path (/home/…/image.png)"
                value={imagePath}
                onChange={(e) => setImagePath(e.target.value)}
                style={{ flex: 1, background: 'transparent', color: 'var(--j-text)', fontSize: 12, fontFamily: 'var(--j-font-mono)', border: 'none', outline: 'none' }}
              />
            </div>
          )}
          <div className="chat-input-row" style={{ padding: 0, border: 'none', background: 'transparent' }}>
            <button
              type="button"
              onClick={() => setShowImagePathInput(!showImagePathInput)}
              className="icon-btn"
              title="Attach image path"
              style={showImagePathInput ? { background: 'var(--j-purple-soft)', color: 'var(--j-purple)' } : {}}
            >
              <ImageIcon size={15} />
            </button>
            <textarea
              rows={1}
              placeholder={isProcessing ? 'Johnny is thinking…' : 'Ask Johnny anything…'}
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSubmit(e as any); } }}
              disabled={isProcessing}
              className="chat-input"
              style={{ resize: 'none' }}
            />
            {isProcessing ? (
              <button
                type="button"
                onClick={onStopGenerating}
                className="send-btn"
                title="Pause / Interrupt Generation"
                style={{
                  background: 'var(--j-amber-soft)',
                  color: 'var(--j-amber)',
                  border: '1px solid var(--j-amber)'
                }}
              >
                <Square size={13} fill="currentColor" />
              </button>
            ) : (
              <button
                type="submit"
                disabled={!inputText.trim() && !imagePath.trim()}
                className="send-btn"
                title="Send Message"
              >
                <Send size={15} />
              </button>
            )}
          </div>
        </form>
      )}
    </div>
  );
};
