/**
 * MultiAgentPanel.tsx — Live multi-agent communication & debate inspector.
 *
 * Features:
 *  - SSE-powered real-time event feed from /api/v1/agent-bus/stream
 *  - Color-coded event types: thoughts, decisions, debates, actions, results
 *  - Inline permission request cards with Approve / Deny buttons
 *  - Auto-scroll to bottom with pause-on-hover
 *  - Severity indicators (info → warn → critical)
 *  - Reconnect logic with exponential backoff
 */

import React, { useEffect, useRef, useState, useCallback } from 'react';
import {
  Brain,
  Gavel,
  Zap,
  CheckCircle,
  XCircle,
  AlertTriangle,
  Shield,
  MessageSquare,
  RefreshCw,
  Pause,
  Play,
  Trash2,
} from 'lucide-react';

const API_BASE = 'http://127.0.0.1:8000/api/v1/agent-bus';

// ── Event Types ────────────────────────────────────────────────────────────────

type AgentEventType =
  | 'AGENT_THOUGHT'
  | 'AGENT_DECISION'
  | 'AGENT_DEBATE'
  | 'AGENT_ACTION'
  | 'AGENT_RESULT'
  | 'PERMISSION_REQUEST'
  | 'PERMISSION_RESPONSE'
  | 'TASK_STATUS'
  | 'SYSTEM_INFO';

interface AgentEvent {
  id:        string;
  type:      AgentEventType;
  agent:     string;
  target:    string;
  content:   string;
  metadata:  Record<string, any>;
  timestamp: number;
  severity:  string;
}

interface PermissionRequest {
  id:          string;
  agent:       string;
  action:      string;
  description: string;
  risk_level:  string;
  metadata:    Record<string, any>;
  arguments?:  Record<string, any>;
  task_id?: string;
  step_number?: number;
  expires_at?: number;
  timestamp:   number;
}

// ── Event Config Map ───────────────────────────────────────────────────────────

const EVENT_CONFIG: Record<AgentEventType, { icon: React.ReactNode; color: string; bg: string; label: string }> = {
  AGENT_THOUGHT:       { icon: <Brain size={11} />,        color: '#818cf8', bg: 'rgba(99,102,241,0.12)',   label: 'Thought'   },
  AGENT_DECISION:      { icon: <Gavel size={11} />,        color: '#34d399', bg: 'rgba(52,211,153,0.10)',   label: 'Decision'  },
  AGENT_DEBATE:        { icon: <AlertTriangle size={11} />,color: '#f59e0b', bg: 'rgba(245,158,11,0.12)',   label: 'Debate'    },
  AGENT_ACTION:        { icon: <Zap size={11} />,          color: '#38bdf8', bg: 'rgba(56,189,248,0.10)',   label: 'Action'    },
  AGENT_RESULT:        { icon: <CheckCircle size={11} />,  color: '#a3e635', bg: 'rgba(163,230,53,0.10)',   label: 'Result'    },
  PERMISSION_REQUEST:  { icon: <Shield size={11} />,       color: '#ef4444', bg: 'rgba(239,68,68,0.15)',    label: 'Permission'},
  PERMISSION_RESPONSE: { icon: <CheckCircle size={11} />,  color: '#94a3b8', bg: 'rgba(148,163,184,0.10)',  label: 'Response'  },
  TASK_STATUS:         { icon: <MessageSquare size={11} />,color: '#c084fc', bg: 'rgba(192,132,252,0.10)',  label: 'Task'      },
  SYSTEM_INFO:         { icon: <RefreshCw size={11} />,    color: '#64748b', bg: 'rgba(100,116,139,0.08)',  label: 'System'    },
};

// ── Helpers ────────────────────────────────────────────────────────────────────

function formatTime(ts: number): string {
  const d = new Date(ts * 1000);
  return d.toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

function agentColor(agent: string): string {
  const palette: Record<string, string> = {
    planner:    '#818cf8',
    executor:   '#38bdf8',
    verifier:   '#34d399',
    researcher: '#c084fc',
    critic:     '#f59e0b',
    system:     '#64748b',
    user:       '#e2e8f0',
  };
  const key = Object.keys(palette).find((k) => agent.toLowerCase().includes(k));
  return key ? palette[key] : '#94a3b8';
}

// ── Permission Card ────────────────────────────────────────────────────────────

const PermissionCard: React.FC<{
  perm: PermissionRequest;
  onResolve: (id: string, approved: boolean) => void;
  resolved?: boolean;
  resolvedApproved?: boolean;
}> = ({ perm, onResolve, resolved, resolvedApproved }) => {
  const riskColor = perm.risk_level === 'critical' ? '#ef4444'
    : perm.risk_level === 'high'     ? '#f97316'
    : perm.risk_level === 'medium'   ? '#f59e0b'
    : '#34d399';

  return (
    <div
      style={{
        borderRadius: 10,
        border: `1px solid ${riskColor}55`,
        background: `rgba(15, 23, 42, 0.95)`,
        padding: '10px 12px',
        marginBottom: 6,
        position: 'relative',
        overflow: 'hidden',
      }}
    >
      {/* Risk stripe */}
      <div style={{ position: 'absolute', left: 0, top: 0, bottom: 0, width: 3, background: riskColor, borderRadius: '10px 0 0 10px' }} />

      <div style={{ paddingLeft: 8 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 4 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <Shield size={12} color={riskColor} />
            <span style={{ fontSize: 10, fontWeight: 800, color: riskColor, textTransform: 'uppercase', letterSpacing: 0.5 }}>
              {perm.risk_level} risk — permission required
            </span>
          </div>
          <span style={{ fontSize: 9, color: '#64748b' }}>{formatTime(perm.timestamp)}</span>
        </div>

        <div style={{ fontSize: 11, fontWeight: 700, color: '#f8fafc', marginBottom: 2 }}>{perm.action || perm.description || 'Requested action'}</div>
        {perm.arguments && <pre style={{ fontSize: 9, color: '#cbd5e1', background: 'rgba(2,6,23,0.7)', borderRadius: 6, padding: 7, margin: '4px 0 8px', whiteSpace: 'pre-wrap', wordBreak: 'break-word', maxHeight: 90, overflow: 'auto' }}>{JSON.stringify(perm.arguments, null, 2)}</pre>}
        {perm.task_id && <div style={{ fontSize: 9, color: '#94a3b8', marginBottom: 8 }}>Task {perm.task_id} · step {perm.step_number}</div>}

        <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
          <span style={{ fontSize: 9, color: agentColor(perm.agent), background: `${agentColor(perm.agent)}18`, padding: '1px 6px', borderRadius: 999, fontWeight: 600 }}>
            {perm.agent}
          </span>
          {resolved ? (
            <span style={{
              marginLeft: 'auto',
              fontSize: 10,
              fontWeight: 700,
              color: resolvedApproved ? '#34d399' : '#ef4444',
              display: 'flex', alignItems: 'center', gap: 4,
            }}>
              {resolvedApproved ? <CheckCircle size={11} /> : <XCircle size={11} />}
              {resolvedApproved ? 'Approved' : 'Denied'}
            </span>
          ) : (
            <div style={{ marginLeft: 'auto', display: 'flex', gap: 6 }}>
              <button
                onClick={() => onResolve(perm.id, false)}
                style={{
                  padding: '3px 10px',
                  borderRadius: 6,
                  background: 'rgba(239,68,68,0.15)',
                  border: '1px solid rgba(239,68,68,0.5)',
                  color: '#f87171',
                  fontSize: 10,
                  fontWeight: 700,
                  cursor: 'pointer',
                  display: 'flex', alignItems: 'center', gap: 4,
                }}
              >
                <XCircle size={10} /> Deny
              </button>
              <button
                onClick={() => onResolve(perm.id, true)}
                style={{
                  padding: '3px 10px',
                  borderRadius: 6,
                  background: 'rgba(52,211,153,0.20)',
                  border: '1px solid rgba(52,211,153,0.6)',
                  color: '#34d399',
                  fontSize: 10,
                  fontWeight: 700,
                  cursor: 'pointer',
                  display: 'flex', alignItems: 'center', gap: 4,
                }}
              >
                <CheckCircle size={10} /> Approve
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

// ── Event Row ──────────────────────────────────────────────────────────────────

const EventRow: React.FC<{
  event: AgentEvent;
  onResolvePermission?: (id: string, approved: boolean) => void;
  resolvedPermissions?: Record<string, boolean>;
}> = ({ event, onResolvePermission, resolvedPermissions }) => {
  const cfg = EVENT_CONFIG[event.type] ?? EVENT_CONFIG.SYSTEM_INFO;

  if (event.type === 'PERMISSION_REQUEST' && event.metadata?.id) {
    const rawRisk = event.metadata.risk_level;
    const mappedRisk = typeof rawRisk === 'string' ? rawRisk : rawRisk >= 3 ? 'critical' : rawRisk >= 2 ? 'high' : 'medium';
    const perm = { agent: event.agent, timestamp: event.timestamp, description: event.content, ...event.metadata, risk_level: mappedRisk } as PermissionRequest;
    const resolved = perm.id in (resolvedPermissions ?? {});
    return (
      <PermissionCard
        perm={perm}
        onResolve={onResolvePermission ?? (() => {})}
        resolved={resolved}
        resolvedApproved={resolvedPermissions?.[perm.id]}
      />
    );
  }

  return (
    <div
      style={{
        display: 'flex',
        gap: 8,
        padding: '5px 6px',
        borderRadius: 7,
        background: cfg.bg,
        marginBottom: 3,
        alignItems: 'flex-start',
        borderLeft: `2px solid ${cfg.color}55`,
      }}
    >
      {/* Type icon */}
      <span style={{ color: cfg.color, marginTop: 1, flexShrink: 0 }}>{cfg.icon}</span>

      {/* Body */}
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 5, marginBottom: 1, flexWrap: 'wrap' }}>
          <span style={{ fontSize: 9, fontWeight: 700, color: agentColor(event.agent), background: `${agentColor(event.agent)}18`, padding: '0 5px', borderRadius: 999 }}>
            {event.agent}
          </span>
          {event.target && (
            <>
              <span style={{ fontSize: 9, color: '#475569' }}>→</span>
              <span style={{ fontSize: 9, fontWeight: 600, color: agentColor(event.target), background: `${agentColor(event.target)}18`, padding: '0 5px', borderRadius: 999 }}>
                {event.target}
              </span>
            </>
          )}
          <span style={{ fontSize: 9, color: cfg.color, fontWeight: 600, marginLeft: 2 }}>[{cfg.label}]</span>
          <span style={{ fontSize: 9, color: '#475569', marginLeft: 'auto', flexShrink: 0 }}>{formatTime(event.timestamp)}</span>
        </div>
        <p style={{ fontSize: 10, color: '#cbd5e1', margin: 0, lineHeight: 1.45, wordBreak: 'break-word', whiteSpace: 'pre-wrap' }}>
          {event.content}
        </p>
      </div>
    </div>
  );
};

// ── Main Panel ─────────────────────────────────────────────────────────────────

export const MultiAgentPanel: React.FC = () => {
  const [events,      setEvents]      = useState<AgentEvent[]>([]);
  const [connected,   setConnected]   = useState(false);
  const [paused,      setPaused]      = useState(false);
  const [filter,      setFilter]      = useState<AgentEventType | 'ALL'>('ALL');
  const [resolvedMap, setResolvedMap] = useState<Record<string, boolean>>({});
  const [agentPrompt, setAgentPrompt] = useState('');
  const [agentReport, setAgentReport] = useState('');
  const [askingAgents, setAskingAgents] = useState(false);

  const scrollRef     = useRef<HTMLDivElement>(null);
  const streamAbortRef = useRef<AbortController | null>(null);
  const pausedRef     = useRef(false);
  const pendingRef    = useRef<AgentEvent[]>([]);

  pausedRef.current = paused;

  // Auto-scroll
  const scrollToBottom = useCallback(() => {
    if (!paused && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [paused]);

  // Load history on mount
  useEffect(() => {
    fetch(`${API_BASE}/history?limit=80`)
      .then((r) => r.json())
      .then((data) => {
        if (Array.isArray(data.events)) {
          setEvents(data.events);
        }
      })
      .catch(() => {});
  }, []);

  // SSE connection
  const connectSSE = useCallback(() => {
    streamAbortRef.current?.abort();
    const controller = new AbortController();
    streamAbortRef.current = controller;
    const parseBlock = (block: string) => {
      let eventName = '';
      let data = '';
      for (const line of block.split('\n')) {
        if (line.startsWith('event:')) eventName = line.slice(6).trim();
        if (line.startsWith('data:')) data += line.slice(5).trim();
      }
      if (eventName === 'connected') { setConnected(true); return; }
      if (!data) return;
      try {
        const parsed: AgentEvent = JSON.parse(data);
        if (pausedRef.current) pendingRef.current.push(parsed);
        else setEvents((prev) => [...prev.slice(-199), parsed]);
      } catch { /* ignore malformed or heartbeat frames */ }
    };
    const consume = async () => {
      try {
        const response = await fetch(`${API_BASE}/stream`, { signal: controller.signal, headers: { Accept: 'text/event-stream' } });
        if (!response.ok || !response.body) throw new Error(`Event stream returned ${response.status}`);
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        while (!controller.signal.aborted) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, '\n');
          const blocks = buffer.split('\n\n');
          buffer = blocks.pop() || '';
          blocks.forEach(parseBlock);
        }
      } catch (error) {
        if (!controller.signal.aborted) setConnected(false);
      } finally {
        if (!controller.signal.aborted) {
          setConnected(false);
          window.setTimeout(() => { if (!streamAbortRef.current?.signal.aborted) connectSSE(); }, 3000);
        }
      }
    };
    void consume();
  }, []);

  useEffect(() => {
    connectSSE();
    return () => {
      streamAbortRef.current?.abort();
    };
  }, [connectSSE]);

  useEffect(() => {
    scrollToBottom();
  }, [events, scrollToBottom]);

  // Resume — flush pending
  const handleResume = () => {
    setPaused(false);
    if (pendingRef.current.length > 0) {
      setEvents((prev) => [...prev, ...pendingRef.current].slice(-200));
      pendingRef.current = [];
    }
  };

  // Permission resolution
  const handleResolve = useCallback(async (id: string, approved: boolean) => {
    try {
      await fetch(`${API_BASE}/permissions/${id}/resolve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ approved }),
      });
      setResolvedMap((prev) => ({ ...prev, [id]: approved }));
    } catch (e) {
      console.error('Permission resolve failed', e);
    }
  }, []);

  const askAgents = async () => {
    const query = agentPrompt.trim();
    if (!query || askingAgents) return;
    setAskingAgents(true);
    setAgentReport('');
    try {
      const response = await fetch('http://127.0.0.1:8000/api/v1/orchestration/deliberate', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query, strategy: 'ensemble' }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || `Request failed (${response.status})`);
      setAgentReport(data.synthesized_recommendation || 'Agents returned no synthesis.');
    } catch (error: any) {
      setAgentReport(`Agent discussion failed: ${error?.message || 'Backend unavailable'}`);
    } finally {
      setAskingAgents(false);
    }
  };

  // Filtered events
  const visible = filter === 'ALL'
    ? events
    : events.filter((e) => e.type === filter);

  const hasPermissions = events.some((e) => e.type === 'PERMISSION_REQUEST');

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', gap: 8 }}>

      {/* ── Header ── */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span
            style={{
              width: 7, height: 7, borderRadius: '50%',
              background: connected ? '#34d399' : '#ef4444',
              boxShadow: connected ? '0 0 6px #34d399' : '0 0 6px #ef4444',
              animation: connected ? 'none' : 'j-pulse 1s infinite',
            }}
          />
          <span style={{ fontSize: 10, fontWeight: 700, color: connected ? '#34d399' : '#ef4444' }}>
            {connected ? 'Live Feed' : 'Reconnecting…'}
          </span>
        </div>

        <span style={{ fontSize: 10, color: '#475569' }}>{events.length} events</span>

        {hasPermissions && (
          <span style={{ fontSize: 9, padding: '1px 7px', borderRadius: 999, background: 'rgba(239,68,68,0.2)', color: '#f87171', border: '1px solid rgba(239,68,68,0.4)', fontWeight: 700, animation: 'j-pulse 1s infinite' }}>
            ⚠ Permissions pending
          </span>
        )}

        <div style={{ marginLeft: 'auto', display: 'flex', gap: 5 }}>
          <button
            onClick={paused ? handleResume : () => setPaused(true)}
            style={{ padding: '3px 8px', borderRadius: 6, background: 'rgba(30,41,59,0.8)', border: '1px solid rgba(148,163,184,0.2)', color: '#94a3b8', fontSize: 9, fontWeight: 600, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 4 }}
          >
            {paused ? <><Play size={9} /> Resume</> : <><Pause size={9} /> Pause</>}
          </button>
          <button
            onClick={() => setEvents([])}
            style={{ padding: '3px 8px', borderRadius: 6, background: 'rgba(30,41,59,0.8)', border: '1px solid rgba(148,163,184,0.2)', color: '#94a3b8', fontSize: 9, fontWeight: 600, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 4 }}
          >
            <Trash2 size={9} /> Clear
          </button>
        </div>
      </div>

      <div style={{ display: 'grid', gap: 6, padding: 8, borderRadius: 9, background: 'rgba(15,23,42,0.72)', border: '1px solid rgba(148,163,184,0.16)' }}>
        <div style={{ fontSize: 10, fontWeight: 700, color: '#c4b5fd' }}>Ask the agents to discuss</div>
        <textarea value={agentPrompt} onChange={(e) => setAgentPrompt(e.target.value)} maxLength={8000}
          placeholder="Ask a question for a multi-model discussion…" rows={2}
          style={{ width: '100%', resize: 'vertical', borderRadius: 7, padding: 7, background: 'rgba(2,6,23,0.8)', color: '#e2e8f0', border: '1px solid rgba(148,163,184,0.2)', fontSize: 11 }} />
        <button onClick={askAgents} disabled={askingAgents || !agentPrompt.trim()}
          style={{ justifySelf: 'end', padding: '4px 10px', borderRadius: 6, border: '1px solid #6366f1', background: askingAgents ? '#312e81' : '#4338ca', color: 'white', fontSize: 10, fontWeight: 700, cursor: askingAgents ? 'wait' : 'pointer', opacity: !agentPrompt.trim() ? 0.5 : 1 }}>
          {askingAgents ? 'Agents discussing…' : 'Start discussion'}
        </button>
        {agentReport && <pre style={{ margin: 0, maxHeight: 130, overflow: 'auto', whiteSpace: 'pre-wrap', wordBreak: 'break-word', fontFamily: 'inherit', fontSize: 10, lineHeight: 1.45, color: '#cbd5e1' }}>{agentReport}</pre>}
      </div>

      {/* ── Filter Chips ── */}
      <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
        {(['ALL', 'AGENT_THOUGHT', 'AGENT_DECISION', 'AGENT_DEBATE', 'AGENT_ACTION', 'PERMISSION_REQUEST'] as const).map((f) => {
          const isActive = filter === f;
          const cfg = f !== 'ALL' ? EVENT_CONFIG[f] : null;
          return (
            <button
              key={f}
              onClick={() => setFilter(f)}
              style={{
                padding: '2px 8px',
                borderRadius: 999,
                fontSize: 9,
                fontWeight: 600,
                cursor: 'pointer',
                background: isActive ? (cfg?.bg ?? 'rgba(99,102,241,0.2)') : 'rgba(15,23,42,0.6)',
                border: `1px solid ${isActive ? (cfg?.color ?? '#818cf8') : 'rgba(148,163,184,0.15)'}`,
                color: isActive ? (cfg?.color ?? '#818cf8') : '#64748b',
                transition: 'all 100ms ease',
              }}
            >
              {f === 'ALL' ? 'All' : EVENT_CONFIG[f].label}
            </button>
          );
        })}
      </div>

      {/* ── Feed ── */}
      <div
        ref={scrollRef}
        style={{
          flex: 1,
          overflowY: 'auto',
          paddingRight: 2,
        }}
        className="no-scrollbar"
      >
        {visible.length === 0 ? (
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', gap: 8, opacity: 0.5 }}>
            <Brain size={28} color="#475569" />
            <span style={{ fontSize: 11, color: '#475569' }}>
              {connected ? 'Waiting for agent activity…' : 'Backend not connected — start the server first.'}
            </span>
          </div>
        ) : (
          visible.map((ev) => (
            <EventRow
              key={ev.id}
              event={ev}
              onResolvePermission={handleResolve}
              resolvedPermissions={resolvedMap}
            />
          ))
        )}
      </div>

      {/* Paused banner */}
      {paused && (
        <button
          onClick={handleResume}
          style={{
            padding: '6px 12px',
            borderRadius: 8,
            background: 'rgba(245,158,11,0.2)',
            border: '1px solid rgba(245,158,11,0.5)',
            color: '#f59e0b',
            fontSize: 10,
            fontWeight: 700,
            cursor: 'pointer',
            textAlign: 'center',
          }}
        >
          ⏸ Feed paused — {pendingRef.current.length} queued · Click to resume
        </button>
      )}
    </div>
  );
};
