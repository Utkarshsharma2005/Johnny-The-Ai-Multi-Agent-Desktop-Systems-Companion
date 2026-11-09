/**
 * PermissionModal.tsx — Floating desktop permission request overlay.
 *
 * Polls /api/v1/agent-bus/permissions at 2-second intervals.
 * When a pending permission request exists, shows a prominent modal
 * that blocks interaction until the user approves or denies.
 *
 * This is the "critical thinking mode" UX — Johnny literally stops
 * and asks the user before doing anything risky.
 */

import React, { useEffect, useState, useCallback, useRef } from 'react';
import { Shield, CheckCircle, XCircle, ChevronDown, ChevronUp, AlertTriangle } from 'lucide-react';

const API_BASE = 'http://127.0.0.1:8000/api/v1/agent-bus';

interface PermissionRequest {
  id:          string;
  agent:       string;
  action:      string;
  description: string;
  risk_level:  'low' | 'medium' | 'high' | 'critical';
  metadata:    Record<string, any>;
  arguments?:  Record<string, any>;
  timestamp:   number;
}

const RISK_COLORS: Record<string, { border: string; bg: string; text: string; glow: string }> = {
  critical: { border: '#ef4444', bg: 'rgba(239,68,68,0.12)', text: '#f87171', glow: '0 0 30px rgba(239,68,68,0.3)' },
  high:     { border: '#f97316', bg: 'rgba(249,115,22,0.10)', text: '#fb923c', glow: '0 0 25px rgba(249,115,22,0.25)' },
  medium:   { border: '#f59e0b', bg: 'rgba(245,158,11,0.10)', text: '#fbbf24', glow: '0 0 20px rgba(245,158,11,0.2)' },
  low:      { border: '#34d399', bg: 'rgba(52,211,153,0.08)', text: '#6ee7b7', glow: '0 0 15px rgba(52,211,153,0.15)' },
};

function agentEmoji(agent: string): string {
  if (agent.includes('planner'))    return '🧠';
  if (agent.includes('executor'))   return '⚡';
  if (agent.includes('verifier'))   return '✅';
  if (agent.includes('researcher')) return '🔍';
  if (agent.includes('critic'))     return '⚖️';
  if (agent.includes('browser'))    return '🌐';
  return '🤖';
}

export const PermissionModal: React.FC = () => {
  const [requests,    setRequests]    = useState<PermissionRequest[]>([]);
  const [resolving,   setResolving]   = useState<string | null>(null);
  const [expanded,    setExpanded]    = useState<Record<string, boolean>>({});
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const backoffUntilRef = useRef<number>(0);

  const fetchPermissions = useCallback(async () => {
    if (Date.now() < backoffUntilRef.current) return;
    try {
      const res = await fetch(`${API_BASE}/permissions`);
      if (res.status === 429) {
        // Rate limited — back off for 6 seconds
        backoffUntilRef.current = Date.now() + 6000;
        return;
      }
      if (!res.ok) return;
      const data = await res.json();
      setRequests(data.permissions ?? []);
    } catch {
      // Backend not running — backoff briefly
      backoffUntilRef.current = Date.now() + 5000;
    }
  }, []);

  useEffect(() => {
    fetchPermissions();
    pollRef.current = setInterval(fetchPermissions, 3000);
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [fetchPermissions]);

  const handleResolve = async (id: string, approved: boolean) => {
    if (resolving) return;
    setResolving(id);
    try {
      await fetch(`${API_BASE}/permissions/${id}/resolve`, {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ approved }),
      });
      setRequests((prev) => prev.filter((r) => r.id !== id));
    } catch (e) {
      console.error('Permission resolve failed:', e);
    } finally {
      setResolving(null);
    }
  };

  if (requests.length === 0) return null;

  const current = requests[0]; // Show most urgent first
  const colors  = RISK_COLORS[current.risk_level] ?? RISK_COLORS.medium;
  const isBusy  = resolving === current.id;

  return (
    <>
      {/* Backdrop blur */}
      <div
        style={{
          position:        'fixed',
          inset:           0,
          background:      'rgba(0, 0, 0, 0.55)',
          backdropFilter:  'blur(3px)',
          zIndex:          9000,
          pointerEvents:   'auto',
        }}
      />

      {/* Modal */}
      <div
        style={{
          position:   'fixed',
          top:        '50%',
          left:       '50%',
          transform:  'translate(-50%, -50%)',
          zIndex:     9001,
          width:      420,
          maxWidth:   'calc(100vw - 32px)',
          background: 'hsla(222, 28%, 8%, 0.98)',
          backdropFilter: 'blur(24px)',
          border:     `1.5px solid ${colors.border}`,
          borderRadius: 16,
          boxShadow:  `0 24px 60px rgba(0,0,0,0.8), ${colors.glow}`,
          overflow:   'hidden',
          fontFamily: 'Inter, system-ui, sans-serif',
        }}
      >
        {/* Risk stripe */}
        <div
          style={{
            height: 4,
            background: `linear-gradient(90deg, ${colors.border}, ${colors.border}88)`,
            width: '100%',
          }}
        />

        <div style={{ padding: '20px 22px' }}>
          {/* Header */}
          <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12, marginBottom: 16 }}>
            <div
              style={{
                width: 40, height: 40, borderRadius: 10,
                background: colors.bg,
                border: `1px solid ${colors.border}`,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                flexShrink: 0,
                animation: current.risk_level === 'critical' ? 'j-pulse 0.8s infinite' : 'none',
              }}
            >
              <Shield size={20} color={colors.text} />
            </div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 3 }}>
                <span
                  style={{
                    fontSize: 10, fontWeight: 800, letterSpacing: 0.8,
                    textTransform: 'uppercase', color: colors.text,
                    background: colors.bg, padding: '1px 7px', borderRadius: 999,
                    border: `1px solid ${colors.border}55`,
                  }}
                >
                  {current.risk_level} risk
                </span>
                {requests.length > 1 && (
                  <span style={{ fontSize: 9, color: '#64748b' }}>
                    +{requests.length - 1} more
                  </span>
                )}
              </div>
              <h3 style={{ fontSize: 14, fontWeight: 800, color: '#f8fafc', margin: 0, lineHeight: 1.2 }}>
                Permission Required
              </h3>
            </div>
          </div>

          {/* Agent + Action */}
          <div
            style={{
              background: 'rgba(15, 23, 42, 0.7)',
              border: '1px solid rgba(148,163,184,0.12)',
              borderRadius: 10,
              padding: '10px 14px',
              marginBottom: 12,
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
              <span style={{ fontSize: 16 }}>{agentEmoji(current.agent)}</span>
              <div>
                <div style={{ fontSize: 10, color: '#64748b', fontWeight: 600, textTransform: 'uppercase', letterSpacing: 0.5 }}>
                  Agent
                </div>
                <div style={{ fontSize: 12, fontWeight: 700, color: '#e2e8f0' }}>
                  {current.agent}
                </div>
              </div>
            </div>
            <div style={{ fontSize: 13, fontWeight: 700, color: colors.text, marginBottom: 4 }}>
              {current.action}
            </div>
            <div style={{ fontSize: 11, color: '#94a3b8', lineHeight: 1.5 }}>
              {current.description}
            </div>
            {current.arguments && (
              <pre style={{ margin: '8px 0 0', padding: '8px', borderRadius: 7, background: 'rgba(0,0,0,0.35)', color: '#cbd5e1', fontSize: 10, whiteSpace: 'pre-wrap', wordBreak: 'break-word', maxHeight: 120, overflow: 'auto' }}>
                {JSON.stringify(current.arguments, null, 2)}
              </pre>
            )}
          </div>

          {/* Expandable metadata */}
          {Object.keys(current.metadata).length > 0 && (
            <div style={{ marginBottom: 12 }}>
              <button
                onClick={() => setExpanded((p) => ({ ...p, [current.id]: !p[current.id] }))}
                style={{
                  background: 'none', border: 'none', color: '#64748b',
                  fontSize: 10, fontWeight: 600, cursor: 'pointer',
                  display: 'flex', alignItems: 'center', gap: 4,
                  padding: 0,
                }}
              >
                {expanded[current.id] ? <ChevronUp size={11} /> : <ChevronDown size={11} />}
                {expanded[current.id] ? 'Hide details' : 'Show technical details'}
              </button>
              {expanded[current.id] && (
                <pre
                  style={{
                    marginTop: 6, padding: '8px 10px', borderRadius: 8,
                    background: 'rgba(0,0,0,0.4)', border: '1px solid rgba(148,163,184,0.1)',
                    fontSize: 10, color: '#64748b', overflow: 'auto',
                    fontFamily: 'ui-monospace, monospace', maxHeight: 100,
                  }}
                >
                  {JSON.stringify(current.metadata, null, 2)}
                </pre>
              )}
            </div>
          )}

          {/* Warning hint for high/critical */}
          {(current.risk_level === 'high' || current.risk_level === 'critical') && (
            <div
              style={{
                display: 'flex', alignItems: 'flex-start', gap: 8,
                padding: '8px 12px', borderRadius: 8,
                background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.25)',
                marginBottom: 16,
              }}
            >
              <AlertTriangle size={13} color="#f87171" style={{ flexShrink: 0, marginTop: 1 }} />
              <span style={{ fontSize: 10, color: '#fca5a5', lineHeight: 1.4 }}>
                This action has a <strong>{current.risk_level}</strong> risk level. Only approve if you understand what the agent is about to do.
              </span>
            </div>
          )}

          {/* Action Buttons */}
          <div style={{ display: 'flex', gap: 10 }}>
            <button
              onClick={() => handleResolve(current.id, false)}
              disabled={isBusy}
              style={{
                flex: 1, padding: '10px 16px', borderRadius: 10,
                background: 'rgba(239,68,68,0.12)', border: '1.5px solid rgba(239,68,68,0.5)',
                color: '#f87171', fontSize: 12, fontWeight: 700,
                cursor: isBusy ? 'not-allowed' : 'pointer',
                display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
                opacity: isBusy ? 0.6 : 1,
                transition: 'all 150ms ease',
              }}
            >
              <XCircle size={14} />
              Deny
            </button>
            <button
              onClick={() => handleResolve(current.id, true)}
              disabled={isBusy}
              style={{
                flex: 1.5, padding: '10px 16px', borderRadius: 10,
                background: 'rgba(52,211,153,0.15)', border: '1.5px solid rgba(52,211,153,0.6)',
                color: '#34d399', fontSize: 12, fontWeight: 700,
                cursor: isBusy ? 'not-allowed' : 'pointer',
                display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
                opacity: isBusy ? 0.6 : 1,
                transition: 'all 150ms ease',
                boxShadow: '0 0 20px rgba(52,211,153,0.15)',
              }}
            >
              <CheckCircle size={14} />
              {isBusy ? 'Processing…' : 'Approve'}
            </button>
          </div>
        </div>
      </div>
    </>
  );
};
