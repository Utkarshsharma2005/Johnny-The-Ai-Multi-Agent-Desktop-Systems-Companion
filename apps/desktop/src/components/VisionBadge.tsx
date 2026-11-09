/**
 * VisionBadge.tsx — screen intelligence cooldown indicator.
 *
 * A pill badge with a circular SVG progress ring showing when the next
 * automatic screen observation fires. Clicking triggers an immediate
 * manual capture. The ring depletes over `cooldownMs` milliseconds.
 */

import React, { useEffect, useRef, useState } from 'react';

interface VisionBadgeProps {
  cooldownMs: number;        // total cooldown duration
  remainingMs: number;       // how many ms left on the current cooldown
  isPaused: boolean;
  onTrigger: () => void;     // manual capture
}

const RING_R  = 8;
const RING_C  = 2 * Math.PI * RING_R; // circumference ≈ 50.3

export const VisionBadge: React.FC<VisionBadgeProps> = ({
  cooldownMs,
  remainingMs,
  isPaused,
  onTrigger,
}) => {
  const [localRemaining, setLocalRemaining] = useState(remainingMs);
  const lastTickRef = useRef(performance.now());
  const rafRef      = useRef<number | null>(null);

  // Count down locally between parent prop updates
  useEffect(() => {
    setLocalRemaining(remainingMs);
  }, [remainingMs]);

  useEffect(() => {
    if (isPaused) return;

    const tick = (now: number) => {
      const elapsed = now - lastTickRef.current;
      lastTickRef.current = now;
      setLocalRemaining((prev) => Math.max(0, prev - elapsed));
      rafRef.current = requestAnimationFrame(tick);
    };
    rafRef.current = requestAnimationFrame(tick);
    return () => {
      if (rafRef.current !== null) cancelAnimationFrame(rafRef.current);
    };
  }, [isPaused, remainingMs]);

  const fraction = cooldownMs > 0 ? Math.max(0, localRemaining / cooldownMs) : 0;
  const dashOffset = RING_C * fraction;
  const secLeft = Math.ceil(localRemaining / 1000);

  return (
    <div
      style={{
        position: 'fixed',
        bottom: 68,
        right: 20,
        zIndex: 'var(--j-z-badge)' as any,
        animation: 'j-wheel-in 200ms var(--j-spring) both',
      }}
    >
      <button
        onClick={onTrigger}
        title={isPaused ? 'Screen observation paused — click to capture' : `Next capture in ${secLeft}s — click for immediate`}
        aria-label={`Screen vision badge. ${isPaused ? 'Paused.' : `${secLeft}s until next capture.`} Click to trigger now.`}
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: 6,
          padding: '3px 10px 3px 6px',
          border: '1px solid var(--j-border-bright)',
          borderRadius: 'var(--j-r-full)',
          background: 'var(--j-glass-bg)',
          backdropFilter: 'var(--j-glass-blur)',
          color: isPaused ? 'var(--j-text-dim)' : 'var(--j-cyan)',
          fontSize: 11,
          fontWeight: 700,
          fontFamily: 'var(--j-font-mono)',
          cursor: 'pointer',
          boxShadow: isPaused ? 'none' : `var(--j-shadow-sm), 0 0 10px hsla(190,80%,55%,0.25)`,
          transition: 'box-shadow 200ms, transform 200ms var(--j-spring)',
        }}
        onMouseEnter={(e) => {
          (e.currentTarget as HTMLButtonElement).style.transform = 'scale(1.06)';
          (e.currentTarget as HTMLButtonElement).style.boxShadow =
            'var(--j-shadow-md), 0 0 16px hsla(190,80%,55%,0.4)';
        }}
        onMouseLeave={(e) => {
          (e.currentTarget as HTMLButtonElement).style.transform = 'scale(1)';
          (e.currentTarget as HTMLButtonElement).style.boxShadow =
            isPaused ? 'none' : 'var(--j-shadow-sm), 0 0 10px hsla(190,80%,55%,0.25)';
        }}
      >
        {/* Progress ring */}
        <svg width={20} height={20} viewBox="0 0 20 20" style={{ flexShrink: 0 }}>
          {/* Track */}
          <circle
            cx={10} cy={10} r={RING_R}
            fill="none"
            stroke="var(--j-border-bright)"
            strokeWidth={2}
          />
          {/* Fill */}
          <circle
            cx={10} cy={10} r={RING_R}
            fill="none"
            stroke={isPaused ? 'var(--j-text-faint)' : 'var(--j-cyan)'}
            strokeWidth={2}
            strokeLinecap="round"
            strokeDasharray={RING_C}
            strokeDashoffset={dashOffset}
            transform="rotate(-90 10 10)"
            style={{ transition: isPaused ? 'none' : 'stroke-dashoffset 0.5s linear' }}
          />
          {/* Eye icon in centre */}
          <text x={10} y={13} textAnchor="middle" fontSize={8} fill="currentColor">
            👁
          </text>
        </svg>

        {/* Label */}
        <span>
          {isPaused ? 'PAUSED' : localRemaining <= 0 ? 'NOW' : `${secLeft}s`}
        </span>
      </button>
    </div>
  );
};
