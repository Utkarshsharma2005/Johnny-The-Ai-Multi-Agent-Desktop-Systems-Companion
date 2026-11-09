/**
 * SpeechBubble.tsx — follows the pet, enters/exits with spring animation.
 * Pure CSS transitions — no Framer Motion dependency.
 */

import React, { useEffect, useRef, useState } from 'react';
import type { AgentState } from '../engine/Director';

interface SpeechBubbleProps {
  text: string;
  visible: boolean;
  agentState: AgentState;
  onDismiss: () => void;
}

const STATE_LABELS: Record<AgentState, string> = {
  IDLE:      'Ready',
  THINKING:  'Llama 70B',
  WORKING:   'Executing',
  COMPLETED: 'Done ✓',
  ERROR:     'Error',
};

const STATE_COLORS: Record<AgentState, string> = {
  IDLE:      'var(--j-green)',
  THINKING:  'var(--j-accent)',
  WORKING:   'var(--j-amber)',
  COMPLETED: 'var(--j-green)',
  ERROR:     'var(--j-red)',
};

export const SpeechBubble: React.FC<SpeechBubbleProps> = ({
  text, visible, agentState, onDismiss,
}) => {
  const [displayed, setDisplayed] = useState(text);
  const [mounted, setMounted] = useState(visible);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (visible) {
      setMounted(true);
      setDisplayed(text);
      // Auto-dismiss after 8s when idle
      if (agentState === 'IDLE') {
        if (timerRef.current) clearTimeout(timerRef.current);
        timerRef.current = setTimeout(onDismiss, 8_000);
      }
    }
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [visible, text, agentState, onDismiss]);

  if (!mounted && !visible) return null;

  return (
    <div
      className="speech-bubble-anchor"
      style={{
        position: 'absolute',
        bottom: '100%',
        left: '50%',
        transform: visible ? 'translateX(-50%) translateY(0) scale(1)' : 'translateX(-50%) translateY(8px) scale(0.95)',
        marginBottom: 14,
        minWidth: 200,
        maxWidth: 280,
        opacity: visible ? 1 : 0,
        transition: 'opacity 220ms var(--j-ease), transform 220ms var(--j-spring)',
        pointerEvents: visible ? 'auto' : 'none',
        zIndex: 50,
      }}
    >
      <div className="speech-bubble">
        {/* Header row */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: 6,
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            {/* State dot */}
            <span style={{
              width: 7,
              height: 7,
              borderRadius: '50%',
              background: STATE_COLORS[agentState],
              display: 'inline-block',
              boxShadow: `0 0 6px ${STATE_COLORS[agentState]}`,
              animation: agentState !== 'IDLE' ? 'j-pulse 1s ease-in-out infinite' : 'none',
            }} />
            <span style={{
              fontWeight: 700,
              fontSize: 12,
              color: 'var(--j-text)',
            }}>Johnny</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <span style={{
              fontSize: 10,
              fontWeight: 600,
              color: STATE_COLORS[agentState],
              background: `color-mix(in srgb, ${STATE_COLORS[agentState]} 15%, transparent)`,
              padding: '1px 7px',
              borderRadius: 'var(--j-r-full)',
              border: `1px solid color-mix(in srgb, ${STATE_COLORS[agentState]} 30%, transparent)`,
            }}>
              {STATE_LABELS[agentState]}
            </span>
            <button
              onClick={onDismiss}
              style={{
                background: 'none',
                border: 'none',
                color: 'var(--j-text-dim)',
                cursor: 'pointer',
                padding: '0 2px',
                fontSize: 14,
                lineHeight: 1,
              }}
              aria-label="Dismiss"
            >×</button>
          </div>
        </div>

        {/* Message text */}
        <p className="speech-bubble-text">{displayed}</p>

        {/* Typing indicator when thinking/working */}
        {(agentState === 'THINKING' || agentState === 'WORKING') && (
          <div style={{ display: 'flex', gap: 3, marginTop: 6 }}>
            {[0, 1, 2].map((i) => (
              <span key={i} style={{
                width: 5, height: 5,
                borderRadius: '50%',
                background: 'var(--j-accent)',
                display: 'inline-block',
                animation: `j-bounce-dot 1s ease-in-out ${i * 0.15}s infinite`,
              }} />
            ))}
          </div>
        )}

        {/* Bubble tail */}
        <div className="speech-bubble-tail" />
      </div>
    </div>
  );
};
