/**
 * ActivityDots.tsx — compact agent-state indicator.
 *
 * A single dot changes colour + animation based on the current agent
 * state. Sits in the top-right corner of the pet sprite (positioned
 * by PetLayer). Fully CSS-driven — no JS timers.
 */

import React from 'react';
import type { AgentState } from '../engine/Director';

interface ActivityDotsProps {
  agentState: AgentState;
}

interface DotConfig {
  color: string;
  glow: string;
  animation: string;
  label: string;
}

const DOT_CONFIG: Record<AgentState, DotConfig> = {
  IDLE: {
    color:     'var(--j-green)',
    glow:      'var(--j-green)',
    animation: 'j-pulse 3s ease-in-out infinite',
    label:     'Idle',
  },
  THINKING: {
    color:     'var(--j-accent)',
    glow:      'var(--j-accent)',
    animation: 'j-pulse 0.7s ease-in-out infinite',
    label:     'Thinking',
  },
  WORKING: {
    color:     'var(--j-amber)',
    glow:      'var(--j-amber)',
    animation: 'j-pulse 0.5s ease-in-out infinite',
    label:     'Working',
  },
  COMPLETED: {
    color:     'var(--j-green)',
    glow:      'var(--j-green)',
    animation: 'j-flash 0.4s ease-out 3',
    label:     'Completed',
  },
  ERROR: {
    color:     'var(--j-red)',
    glow:      'var(--j-red)',
    animation: 'j-pulse 0.3s ease-in-out infinite',
    label:     'Error',
  },
};

export const ActivityDots: React.FC<ActivityDotsProps> = ({ agentState }) => {
  const cfg = DOT_CONFIG[agentState];

  return (
    <div
      role="status"
      aria-label={`Johnny status: ${cfg.label}`}
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 3,
        padding: '2px 6px',
        borderRadius: 'var(--j-r-full)',
        background: 'var(--j-bg-base)',
        border: '1px solid var(--j-border)',
        boxShadow: 'var(--j-shadow-sm)',
      }}
    >
      {/* Main state dot */}
      <span
        style={{
          width: 7,
          height: 7,
          borderRadius: '50%',
          background: cfg.color,
          boxShadow: `0 0 5px ${cfg.glow}`,
          animation: cfg.animation,
          display: 'inline-block',
          flexShrink: 0,
        }}
      />
      {/* State label (tiny, mono) */}
      <span
        style={{
          fontSize: 9,
          fontFamily: 'var(--j-font-mono)',
          fontWeight: 700,
          color: cfg.color,
          letterSpacing: '0.03em',
          lineHeight: 1,
          textTransform: 'uppercase',
        }}
      >
        {cfg.label}
      </span>
    </div>
  );
};
