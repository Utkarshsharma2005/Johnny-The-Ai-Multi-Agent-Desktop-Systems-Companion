/**
 * PetLayer.tsx — The physics-driven pet overlay component.
 *
 * Key features:
 *  1. Character Switcher Synchronized with PetEngine via setCharacter() effect.
 *  2. 3-Mode Notification Light on the moving character:
 *       🟢 Green  — Ready / Idle
 *       🟡 Yellow — Working / Medium / Complex Task
 *       🔴 Red    — Critical / Browser Automation / Error
 *  3. Tap/Click character stops movement and opens reference-styled SkillWheel.
 *  4. Horizontal margins ensure the SkillWheel is never clipped on screen edges.
 */

import React, { useEffect, useRef, useState, useCallback } from 'react';
import { PetEngine } from '../engine/PetEngine';
import { Director, type AgentState } from '../engine/Director';
import { SpeechBubble } from './SpeechBubble';
import { SkillWheel, type WheelAction } from './SkillWheel';
import { playWheelSound } from '../engine/wheelSounds';

const PET_SIZE = 96; // logical px — square bounding box

export interface PetLayerProps {
  agentState: AgentState;
  speechText: string;
  character?: string;
  isConsoleOpen?: boolean;
  notificationMode?: 'green' | 'yellow' | 'red';
  onToggleConsole: () => void;
  onOpenConsole: (tab?: string) => void;
  onTriggerVision: () => void;
  onOpenTasks: () => void;
  onOpenMemory: () => void;
  onOpenTools: () => void;
  onOpenSettings: () => void;
  onSelectCharacter?: (char: string) => void;
  onTerminateTasks?: () => Promise<boolean>;
}

export const PetLayer: React.FC<PetLayerProps> = ({
  agentState,
  speechText,
  character = 'albedo',
  isConsoleOpen = false,
  notificationMode = 'green',
  onToggleConsole,
  onOpenConsole,
  onTriggerVision,
  onOpenTasks,
  onOpenMemory,
  onOpenTools,
  onOpenSettings,
  onSelectCharacter,
  onTerminateTasks,
}) => {
  const petRef   = useRef<HTMLDivElement>(null);
  const engineRef = useRef<PetEngine | null>(null);
  const dirRef    = useRef<Director | null>(null);

  const [wheelOpen, setWheelOpen] = useState(false);
  const [bubbleVisible, setBubbleVisible] = useState(true);

  /* ─── Bootstrap engine + director ──────────────────────────────── */
  useEffect(() => {
    const engine = new PetEngine({ size: PET_SIZE, character });
    const director = new Director(engine);
    engineRef.current = engine;
    dirRef.current = director;

    if (petRef.current) {
      engine.register(petRef.current);
    }
    director.start();

    return () => {
      director.stop();
      engine.unregister();
    };
  }, []);

  /* ─── Forward agent state → Director ───────────────────────────── */
  useEffect(() => {
    dirRef.current?.setAgentState(agentState);
  }, [agentState]);

  /* ─── Synchronize character change to engine ───────────────────── */
  useEffect(() => {
    engineRef.current?.setCharacter(character);
  }, [character]);

  /* ─── Pause new ambient behaviors; let current movement finish ──── */
  useEffect(() => {
    dirRef.current?.setBehaviorsSuspended(wheelOpen);
  }, [wheelOpen]);

  const closeWheel = useCallback(() => {
    if (!wheelOpen) return;
    playWheelSound('close');
    setWheelOpen(false);
  }, [wheelOpen]);

  const toggleWheel = useCallback(() => {
    if (wheelOpen) closeWheel();
    else {
      playWheelSound('open');
      setWheelOpen(true);
    }
  }, [closeWheel, wheelOpen]);

  /* ─── Pointer capture drag ──────────────────────────────────────── */
  const handlePointerDown = useCallback((e: React.PointerEvent<HTMLDivElement>) => {
    if (e.button !== 0) return;
    e.currentTarget.setPointerCapture(e.pointerId);
    dirRef.current?.beginDrag(e.clientX, e.clientY);
    closeWheel();
  }, [closeWheel]);

  const handlePointerMove = useCallback((e: React.PointerEvent<HTMLDivElement>) => {
    if (!e.buttons) return;
    dirRef.current?.dragTo(e.clientX, e.clientY);
  }, []);

  const handlePointerUp = useCallback((e: React.PointerEvent<HTMLDivElement>) => {
    dirRef.current?.endDrag(e.clientX, e.clientY);
  }, []);

  /* ─── Click on pet → open skill wheel & freeze ─────────────────── */
  const handleClick = useCallback((e: React.MouseEvent) => {
    e.stopPropagation();
    toggleWheel();
    setBubbleVisible(true);
  }, [toggleWheel]);

  /* ─── Skill wheel handlers ──────────────────────────────────────── */
  const handleWheelAction = useCallback((action: WheelAction) => {
    setWheelOpen(false);
    playWheelSound('close');
    switch (action) {
      case 'chat':          onOpenConsole('chat');          break;
      case 'vision':        onOpenConsole('screen');        break;
      case 'browser':       onOpenConsole('browser');       break;
      case 'tools':         onOpenConsole('tools');         break;
      case 'memory':        onOpenConsole('memory');        break;
      case 'tasks':         onOpenConsole('tasks');         break;
      case 'orchestration': onOpenConsole('models');        break;
      case 'settings':      onOpenConsole('settings');      break;
      case 'requirements': onOpenConsole('reqs');            break;
      case 'verify':       onOpenConsole('verify');          break;
      case 'telemetry':    onOpenConsole('telemetry');       break;
    }
  }, [onOpenConsole]);

  const getNotificationColor = () => {
    if (notificationMode === 'red') return '#ef4444';
    if (notificationMode === 'yellow') return '#f59e0b';
    return '#10b981';
  };

  return (
    <div className="pet-layer" aria-label="Johnny AI Pet">
      {/* ── The pet div — engine writes transform directly ─────────── */}
      <div
        ref={petRef}
        className="pet"
        data-state="idle"
        data-face="right"
        data-frame="0"
        data-dragging="false"
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
        onClick={handleClick}
        aria-label="Johnny, your AI companion. Click to open action wheel."
        role="button"
        tabIndex={0}
        onKeyDown={(e) => e.key === 'Enter' && toggleWheel()}
        style={{ width: PET_SIZE, height: PET_SIZE, position: 'absolute', left: 0, top: 0, touchAction: 'none' }}
      >
        {/* ── 3-Mode Notification Light (Green / Yellow / Red) ─────── */}
        <div
          title={`Status: ${notificationMode.toUpperCase()} (${notificationMode === 'green' ? 'Ready' : notificationMode === 'yellow' ? 'Processing Task' : 'Critical / Browser Active'})`}
          style={{
            position: 'absolute',
            top: 4,
            left: 4,
            width: 14,
            height: 14,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 20,
            pointerEvents: 'none',
          }}
        >
          {/* Animated halo */}
          <span
            style={{
              position: 'absolute',
              width: 16,
              height: 16,
              borderRadius: '50%',
              background: `${getNotificationColor()}44`,
              boxShadow: `0 0 10px ${getNotificationColor()}`,
              animation: notificationMode !== 'green' ? 'j-wheel-in 0.8s infinite alternate' : 'none',
            }}
          />
          {/* Solid LED bead */}
          <span
            style={{
              width: 7,
              height: 7,
              borderRadius: '50%',
              background: getNotificationColor(),
              boxShadow: `0 0 6px ${getNotificationColor()}`,
              border: '1px solid rgba(255, 255, 255, 0.8)',
            }}
          />
        </div>

        {/* ── Skill Wheel (Centered directly on the frozen pet) ────── */}
        {wheelOpen && (
          <SkillWheel
            character={character}
            onSelectCharacter={onSelectCharacter}
            onAction={handleWheelAction}
            onClose={closeWheel}
            onPetPosition={(callback) => dirRef.current?.onPosition(callback) ?? (() => undefined)}
            agentState={agentState}
            notificationMode={notificationMode}
            onTerminateTasks={onTerminateTasks}
          />
        )}

        {/* ── Speech bubble (anchored directly above pet) ───────────── */}
        <SpeechBubble
          text={speechText}
          visible={bubbleVisible && !wheelOpen}
          agentState={agentState}
          onDismiss={() => setBubbleVisible(false)}
        />

        {/* ── Pet body with Shimeji sprite image ───────────────────── */}
        <div className="pet-body" style={{ width: '100%', height: '100%', position: 'relative' }}>
          <img
            className="pet-sprite-img"
            src={`/assets/${character}/walk1.png`}
            alt={character}
            draggable={false}
            style={{
              width: '100%',
              height: '100%',
              objectFit: 'contain',
              objectPosition: 'bottom center',
              userSelect: 'none',
              filter: notificationMode === 'red'
                ? 'drop-shadow(0 0 20px rgba(239, 68, 68, 0.9)) drop-shadow(0 0 6px rgba(239, 68, 68, 0.6))'
                : notificationMode === 'yellow'
                ? 'drop-shadow(0 0 20px rgba(245, 158, 11, 0.9)) drop-shadow(0 0 6px rgba(245, 158, 11, 0.6))'
                : 'drop-shadow(0 0 16px rgba(16, 185, 129, 0.65)) drop-shadow(0 4px 12px rgba(0, 0, 0, 0.45))',
              transition: 'filter 0.3s ease, transform 0.1s linear',
            }}
          />
        </div>
      </div>
    </div>
  );
};
