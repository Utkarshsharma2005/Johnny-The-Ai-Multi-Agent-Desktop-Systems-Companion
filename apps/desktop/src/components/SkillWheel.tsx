/**
 * SkillWheel.tsx — pet-following radial action menu.
 *
 * Architecture:
 *  - Eight primary console destinations with a secondary More ring.
 *  - Four labeled quick actions and status in the center hub.
 *  - Tracks and clamps to the pet position supplied by PetEngine.
 */

import React, { useState, useEffect, useRef } from 'react';
import {
  MessageSquare,
  Eye,
  Globe,
  Wrench,
  Database,
  Terminal,
  Users,
  Settings,
  OctagonAlert,
  X,
  Sparkles,
  ArrowLeft,
  CheckCircle2,
  ClipboardCheck,
  Cpu,
  Activity,
} from 'lucide-react';
import type { AgentState } from '../engine/Director';
import type { PetPosition } from '../engine/PetEngine';
import { playWheelSound } from '../engine/wheelSounds';

export type WheelAction = 'chat' | 'vision' | 'browser' | 'tools' | 'memory' | 'tasks' | 'orchestration' | 'settings' | 'requirements' | 'verify' | 'telemetry';

interface SkillWheelProps {
  character: string;
  onSelectCharacter?: (char: string) => void;
  onAction: (action: WheelAction) => void;
  onClose: () => void;
  agentState: AgentState;
  notificationMode?: 'green' | 'yellow' | 'red';
  onTerminateTasks?: () => Promise<boolean>;
  onPetPosition: (callback: (position: PetPosition) => void) => () => void;
}

interface SectorDef {
  id: WheelAction | 'characters' | 'more';
  label: string;
  icon: React.ReactNode;
  accent: string;
}

const MAIN_SECTORS: SectorDef[] = [
  { id: 'chat',             label: 'Chat',        icon: <MessageSquare size={16} />, accent: '#6366f1' },
  { id: 'vision',           label: 'Vision',      icon: <Eye size={16} />,           accent: '#06b6d4' },
  { id: 'browser',          label: 'Browser',     icon: <Globe size={16} />,         accent: '#3b82f6' },
  { id: 'tasks',            label: 'Tasks',       icon: <Terminal size={16} />,      accent: '#f59e0b' },
  { id: 'memory',           label: 'Memory',      icon: <Database size={16} />,      accent: '#a855f7' },
  { id: 'tools',            label: 'Tools',       icon: <Wrench size={16} />,        accent: '#38bdf8' },
  { id: 'verify',           label: 'Verify',      icon: <CheckCircle2 size={16} />, accent: '#22c55e' },
  { id: 'more',             label: 'More',        icon: <Sparkles size={16} />,      accent: '#ec4899' },
];

const MORE_SECTORS: SectorDef[] = [
  { id: 'requirements', label: 'Requirements', icon: <ClipboardCheck size={16} />, accent: '#38bdf8' },
  { id: 'orchestration',label: 'Models',       icon: <Cpu size={16} />,             accent: '#a855f7' },
  { id: 'telemetry',    label: 'Telemetry',    icon: <Activity size={16} />,        accent: '#06b6d4' },
  { id: 'settings',     label: 'Settings',     icon: <Settings size={16} />,        accent: '#94a3b8' },
  { id: 'characters',   label: 'Characters',   icon: <Sparkles size={16} />,        accent: '#ec4899' },
];

const CHARACTERS = [
  { id: 'albedo',    name: 'Albedo',    role: 'Calm Alchemist' },
  { id: 'deadpool',  name: 'Deadpool',  role: 'Snarky Partner' },
  { id: 'klee',      name: 'Klee',      role: 'Curious Spark' },
  { id: 'spongebob', name: 'SpongeBob', role: 'High Energy' },
];

const R_INNER = 72;   // Inner circle radius (center hub)
const R_OUTER = 135;  // Outer ring radius; matches the pet engine's edge clearance

function polarToCartesian(centerX: number, centerY: number, radius: number, angleInDegrees: number) {
  const angleInRadians = ((angleInDegrees - 90) * Math.PI) / 180.0;
  return {
    x: centerX + radius * Math.cos(angleInRadians),
    y: centerY + radius * Math.sin(angleInRadians),
  };
}

function createWedgePath(
  centerX: number,
  centerY: number,
  innerR: number,
  outerR: number,
  startDeg: number,
  endDeg: number
) {
  const p1 = polarToCartesian(centerX, centerY, outerR, endDeg);
  const p2 = polarToCartesian(centerX, centerY, outerR, startDeg);
  const p3 = polarToCartesian(centerX, centerY, innerR, startDeg);
  const p4 = polarToCartesian(centerX, centerY, innerR, endDeg);

  const largeArcFlag = endDeg - startDeg <= 180 ? '0' : '1';

  return `
    M ${p1.x} ${p1.y}
    A ${outerR} ${outerR} 0 ${largeArcFlag} 0 ${p2.x} ${p2.y}
    L ${p3.x} ${p3.y}
    A ${innerR} ${innerR} 0 ${largeArcFlag} 1 ${p4.x} ${p4.y}
    Z
  `;
}

export const SkillWheel: React.FC<SkillWheelProps> = ({
  character = 'albedo',
  onSelectCharacter,
  onAction,
  onClose,
  agentState,
  notificationMode = 'green',
  onTerminateTasks,
  onPetPosition,
}) => {
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);
  const [viewMode, setViewMode] = useState<'hub' | 'characters' | 'more'>('hub');
  const [terminating, setTerminating] = useState(false);
  const [wheelScale, setWheelScale] = useState(1);
  const ref = useRef<HTMLDivElement>(null);
  const lastPosition = useRef<PetPosition>({ x: 0, y: 0, size: 96 });
  const sectors = viewMode === 'more' ? MORE_SECTORS : MAIN_SECTORS;

  // Close on Escape or click outside
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    const clickOutside = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        onClose();
      }
    };
    window.addEventListener('keydown', handler);
    const timer = setTimeout(() => {
      window.addEventListener('mousedown', clickOutside);
    }, 60);

    return () => {
      clearTimeout(timer);
      window.removeEventListener('keydown', handler);
      window.removeEventListener('mousedown', clickOutside);
    };
  }, [onClose]);

  // Keep the whole wheel visible and follow the engine's live pet position.
  useEffect(() => {
    const placeWheel = (position: PetPosition, scale: number) => {
      const element = ref.current;
      if (!element) return;
      const radius = (R_OUTER + 5) * scale;
      const centerX = position.x + position.size / 2;
      const centerY = position.y + position.size / 2;
      const clampCenter = (value: number, extent: number, max: number) =>
        max <= extent * 2 ? max / 2 : Math.max(extent, Math.min(max - extent, value));
      const offsetX = clampCenter(centerX, radius + 8, window.innerWidth) - centerX;
      const offsetY = clampCenter(centerY, radius + 8, window.innerHeight) - centerY;
      element.style.left = `calc(50% + ${offsetX}px)`;
      element.style.top = `calc(50% + ${offsetY}px)`;
    };
    const updatePosition = (position = lastPosition.current) => {
      lastPosition.current = position;
      placeWheel(position, wheelScale);
    };
    const updateScale = () => {
      const scale = Math.max(0.1, Math.min(1, (Math.min(window.innerWidth, window.innerHeight) - 16) / ((R_OUTER + 5) * 2)));
      setWheelScale(scale);
      placeWheel(lastPosition.current, scale);
    };
    const unsubscribe = onPetPosition(updatePosition);
    updateScale();
    window.addEventListener('resize', updateScale);
    return () => {
      unsubscribe();
      window.removeEventListener('resize', updateScale);
    };
  }, [onPetPosition, wheelScale]);

  const handleTerminate = async (e: React.MouseEvent) => {
    e.stopPropagation();
    if (terminating) return;
    setTerminating(true);
    try {
      await onTerminateTasks?.();
    } finally {
      setTimeout(() => setTerminating(false), 800);
    }
  };

  const getStatusColor = () => {
    if (notificationMode === 'red') return '#ef4444';
    if (notificationMode === 'yellow') return '#f59e0b';
    return '#10b981';
  };

  const getStatusLabel = () => {
    if (notificationMode === 'red') return 'Critical / Browser';
    if (notificationMode === 'yellow') return 'Working / Task';
    return 'Ready / Idle';
  };

  const numSectors = sectors.length;
  const sliceAngle = 360 / numSectors;
  const gap = 2.0; // visual separation gap between annular sectors

  return (
    <div
      ref={ref}
      onPointerDown={(e) => e.stopPropagation()}
      onClick={(e) => e.stopPropagation()}
      style={{
        position: 'absolute',
        width: 0,
        height: 0,
        zIndex: 120,
        pointerEvents: 'auto',
        userSelect: 'none',
        transform: `scale(${wheelScale})`,
        transformOrigin: 'center center',
      }}
      role="menu"
      aria-label="Johnny Character Action Wheel"
    >
      {/* ── Outer Annular Sector Ring (SVG) ────────────────────────── */}
      <svg
        width={R_OUTER * 2 + 10}
        height={R_OUTER * 2 + 10}
        viewBox={`${-(R_OUTER + 5)} ${-(R_OUTER + 5)} ${(R_OUTER + 5) * 2} ${(R_OUTER + 5) * 2}`}
        style={{
          position: 'absolute',
          left: -(R_OUTER + 5),
          top: -(R_OUTER + 5),
          overflow: 'visible',
          filter: 'drop-shadow(0 12px 32px rgba(0, 0, 0, 0.7))',
        }}
      >
        <defs>
          <radialGradient id="skill-wheel-ring-bg" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="hsla(230, 24%, 14%, 0.94)" />
            <stop offset="100%" stopColor="hsla(230, 26%, 8%, 0.96)" />
          </radialGradient>
        </defs>

        {sectors.map((sector, i) => {
          const startAngle = i * sliceAngle + gap / 2;
          const endAngle = (i + 1) * sliceAngle - gap / 2;
          const isHovered = hoveredIndex === i;
          const pathD = createWedgePath(0, 0, R_INNER + 2, R_OUTER, startAngle, endAngle);

          return (
            <path
              key={sector.id}
              d={pathD}
              fill={isHovered ? 'hsla(230, 30%, 22%, 0.98)' : 'url(#skill-wheel-ring-bg)'}
              stroke={isHovered ? sector.accent : 'hsla(220, 20%, 30%, 0.45)'}
              strokeWidth={isHovered ? '1.8' : '1'}
              style={{
                cursor: 'pointer',
                transition: 'fill 140ms ease, stroke 140ms ease, filter 140ms ease',
                filter: isHovered ? `drop-shadow(0 0 10px ${sector.accent}77)` : 'none',
              }}
              onMouseEnter={() => {
                setHoveredIndex(i);
                playWheelSound('hover');
              }}
              onMouseLeave={() => setHoveredIndex(null)}
              onClick={() => {
                playWheelSound('select');
                if (sector.id === 'more') {
                  setViewMode('more');
                } else if (sector.id === 'characters') {
                  setViewMode('characters');
                } else {
                  onAction(sector.id as WheelAction);
                }
              }}
              role="menuitem"
              aria-label={sector.label}
              tabIndex={0}
              onKeyDown={(event) => {
                if (event.key === 'Enter' || event.key === ' ') {
                  event.preventDefault();
                  playWheelSound('select');
                  if (sector.id === 'more') setViewMode('more');
                  else if (sector.id === 'characters') setViewMode('characters');
                  else onAction(sector.id as WheelAction);
                }
              }}
            />
          );
        })}
      </svg>

      {/* ── Outer Icons Placed over Wedges ─────────────────────────── */}
      {sectors.map((sector, i) => {
        const midAngle = i * sliceAngle + sliceAngle / 2;
        const iconRadius = (R_INNER + R_OUTER) / 2;
        const pos = polarToCartesian(0, 0, iconRadius, midAngle);
        const isHovered = hoveredIndex === i;

        return (
          <div
            key={sector.id}
            onMouseEnter={() => setHoveredIndex(i)}
            onMouseLeave={() => setHoveredIndex(null)}
            style={{
              position: 'absolute',
              left: pos.x,
              top: pos.y,
              transform: `translate(-50%, -50%) scale(${isHovered ? 1.2 : 1})`,
              color: isHovered ? sector.accent : '#cbd5e1',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              cursor: 'pointer',
              pointerEvents: 'none',
              transition: 'transform 140ms cubic-bezier(0.34, 1.56, 0.64, 1), color 140ms ease',
            }}
          >
            {sector.icon}
            {isHovered && (
              <span
                style={{
                  position: 'absolute',
                  top: -16,
                  background: 'rgba(15, 23, 42, 0.95)',
                  border: `1px solid ${sector.accent}88`,
                  borderRadius: 999,
                  padding: '1px 6px',
                  fontSize: 9,
                  fontWeight: 700,
                  color: sector.accent,
                  whiteSpace: 'nowrap',
                  pointerEvents: 'none',
                  boxShadow: '0 2px 8px rgba(0,0,0,0.5)',
                }}
              >
                {sector.label}
              </span>
            )}
          </div>
        );
      })}

      {/* ── Center Hub (Inner Circle) ──────────────────────────────── */}
      <div
        style={{
          position: 'absolute',
          width: R_INNER * 2,
          height: R_INNER * 2,
          boxSizing: 'border-box',
          borderRadius: '50%',
          background: 'radial-gradient(circle at 50% 30%, rgba(28, 36, 55, 0.98), rgba(9, 12, 21, 0.99) 72%)',
          backdropFilter: 'blur(24px)',
          border: '1.5px solid hsla(220, 20%, 35%, 0.55)',
          boxShadow: 'inset 0 1px 0 rgba(255,255,255,.08), inset 0 0 24px rgba(0,0,0,.52), 0 10px 32px rgba(0,0,0,.48)',
          transform: 'translate(-50%, -50%)',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          overflow: 'hidden',
          padding: 8,
          zIndex: 10,
        }}
      >
        {viewMode === 'hub' ? (
          <>
            {/* Background Character Watermark Avatar */}
            <img
              src={`/assets/${character}/walk1.png`}
              alt={character}
              style={{
                position: 'absolute',
                width: 60,
                height: 60,
                objectFit: 'contain',
                opacity: 0.18,
                pointerEvents: 'none',
                filter: 'grayscale(30%)',
              }}
            />

            {/* Notification LED dot (3 Modes: Green, Yellow, Red) */}
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 5,
                marginBottom: 2,
                zIndex: 2,
              }}
              title={`Notification Mode: ${getStatusLabel()}`}
            >
              <span
                style={{
                  width: 7,
                  height: 7,
                  borderRadius: '50%',
                  background: getStatusColor(),
                  boxShadow: `0 0 8px ${getStatusColor()}`,
                  animation: notificationMode !== 'green' ? 'j-pulse 1s ease infinite' : 'none',
                }}
              />
              <span style={{ fontSize: 9, color: getStatusColor(), fontWeight: 700, textTransform: 'uppercase', letterSpacing: 0.5 }}>
                {notificationMode}
              </span>
            </div>

            {/* Character Name */}
            <div
              style={{
                fontSize: 12,
                fontWeight: 800,
                color: '#f8fafc',
                letterSpacing: 0.5,
                zIndex: 2,
                textTransform: 'capitalize',
                lineHeight: 1.1,
              }}
            >
              {character}
            </div>

            {/* Status text */}
            <div
              style={{
                fontSize: 9,
                color: '#94a3b8',
                marginBottom: 6,
                zIndex: 2,
              }}
            >
              {getStatusLabel()}
            </div>

            {/* Quick actions: common console destinations, task control, and character switcher. */}
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(2, minmax(0, 1fr))',
                gap: 3,
                zIndex: 2,
                width: '100%',
                marginBottom: 3,
              }}
            >
              {[
                { label: 'Chat', icon: <MessageSquare size={10} />, action: () => onAction('chat'), color: '#818cf8' },
                { label: 'Models', icon: <Users size={10} />, action: () => onAction('orchestration'), color: '#c084fc' },
                { label: 'Stop', icon: <OctagonAlert size={10} />, action: handleTerminate, color: '#f87171', disabled: terminating },
                { label: 'Character', icon: <Sparkles size={10} />, action: () => setViewMode('characters'), color: '#f472b6' },
              ].map((quick) => (
                <button
                  key={quick.label}
                  type="button"
                  onClick={quick.action}
                  disabled={quick.disabled}
                  title={quick.label === 'Stop' ? 'Terminate running tasks' : quick.label}
                  style={{
                    minWidth: 0, height: 22, padding: '0 4px', borderRadius: 7,
                    background: 'rgba(30, 41, 59, 0.82)', border: `1px solid ${quick.color}55`,
                    color: quick.color, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 3,
                    cursor: quick.disabled ? 'not-allowed' : 'pointer', fontSize: 8, fontWeight: 700,
                    whiteSpace: 'nowrap',
                  }}
                >
                  {quick.icon}<span>{quick.label}</span>
                </button>
              ))}
            </div>

            {/* Close Button (×) */}
            <button
              onClick={onClose}
              title="Close Menu (Esc)"
              style={{
                width: 18,
                height: 18,
                borderRadius: '50%',
                background: 'rgba(30, 41, 59, 0.7)',
                border: '1px solid rgba(148, 163, 184, 0.3)',
                color: '#94a3b8',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                cursor: 'pointer',
                padding: 0,
                zIndex: 2,
              }}
            >
              <X size={10} />
            </button>
          </>
        ) : (
          /* Character Switcher Mode inside Inner Hub */
          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              width: '100%',
              height: '100%',
              justifyContent: 'space-between',
              padding: 4,
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 10, fontWeight: 700, color: '#ec4899' }}>
              <button
                onClick={() => setViewMode('hub')}
                style={{ background: 'none', border: 'none', color: '#94a3b8', cursor: 'pointer', padding: 0 }}
                title="Back"
              >
                <ArrowLeft size={11} />
              </button>
              <span>{viewMode === 'characters' ? 'Characters' : 'More tools'}</span>
            </div>

            {/* 2x2 Character Grid */}
            {viewMode === 'characters' ? <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(2, 1fr)',
                gap: 4,
                width: '100%',
                padding: '0 2px',
              }}
            >
              {CHARACTERS.map((c) => {
                const isActive = character === c.id;
                return (
                  <button
                    key={c.id}
                    onClick={() => {
                      onSelectCharacter?.(c.id);
                      setViewMode('hub');
                    }}
                    title={c.name}
                    style={{
                      display: 'flex',
                      flexDirection: 'column',
                      alignItems: 'center',
                      padding: 2,
                      borderRadius: 6,
                      background: isActive ? 'rgba(99, 102, 241, 0.35)' : 'rgba(30, 41, 59, 0.7)',
                      border: isActive ? '1px solid #6366f1' : '1px solid rgba(148, 163, 184, 0.2)',
                      cursor: 'pointer',
                      transition: 'transform 100ms ease',
                    }}
                  >
                    <img
                      src={`/assets/${c.id}/walk1.png`}
                      alt={c.name}
                      style={{ width: 22, height: 22, objectFit: 'contain' }}
                    />
                    <span style={{ fontSize: 8, fontWeight: 700, color: isActive ? '#818cf8' : '#e2e8f0', marginTop: 1 }}>
                      {c.name}
                    </span>
                  </button>
                );
              })}
            </div> : <p style={{ margin: 0, padding: '0 8px', textAlign: 'center', fontSize: 9, lineHeight: 1.35, color: '#94a3b8' }}>Choose a console section from the outer ring.</p>}

            <button
              onClick={() => setViewMode('hub')}
              style={{
                fontSize: 9,
                color: '#94a3b8',
                background: 'none',
                border: 'none',
                cursor: 'pointer',
                padding: 0,
              }}
            >
              Cancel
            </button>
          </div>
        )}
      </div>
    </div>
  );
};
