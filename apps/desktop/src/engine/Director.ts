/**
 * Director.ts — Behavior scheduler for Johnny's pet.
 *
 * Owns:
 *   - One rAF loop (the ONLY loop in the app — never create another).
 *   - Weighted random behavior picks with cooldown tracking.
 *   - Variety de-weighting (last 4 behaviors get ×0.25 weight).
 *   - Agent-state bus: listens to agentState prop and triggers
 *     the matching event behavior, aborting ambient behaviors.
 *
 * Usage:
 *   const dir = new Director(engine);
 *   dir.start();
 *   dir.setAgentState('thinking'); // from parent component
 *   dir.stop();                    // on unmount
 */

import { PetEngine, type PetPhysicsState, type PetPosition } from './PetEngine';
import {
  BEHAVIORS,
  BEHAVIORS_BY_ID,
  type BehaviorCtx,
  type BehaviorDef,
  wait,
} from './behaviors';

export type AgentState =
  | 'IDLE'
  | 'THINKING'
  | 'WORKING'
  | 'COMPLETED'
  | 'ERROR';

const AGENT_STATE_TO_BEHAVIOR: Record<AgentState, string | null> = {
  IDLE:      null,
  THINKING:  'agent-thinking',
  WORKING:   'agent-working',
  COMPLETED: 'task-success-jump',
  ERROR:     'error-ear-droop',
};

export class Director {
  private engine: PetEngine;
  private rafId: number | null = null;
  private _running = false;
  private _agentState: AgentState = 'IDLE';
  private _behaviorsSuspended = false;

  // Behavior scheduling
  private _nextDecisionAt = 0;
  private _recent: string[] = [];
  private _cooldownUntil = new Map<string, number>();
  private _currentCtrl: AbortController | null = null;
  private _currentBehavior: string | null = null;

  constructor(engine: PetEngine) {
    this.engine = engine;
  }

  /* ─── Lifecycle ────────────────────────────────────────────────── */

  start(): void {
    if (this._running) return;
    this._running = true;
    this._nextDecisionAt = performance.now() + 2_500 + Math.random() * 2_500;
    this._loop(performance.now());
  }

  stop(): void {
    this._running = false;
    if (this.rafId !== null) cancelAnimationFrame(this.rafId);
    this.rafId = null;
    this._abortCurrent();
  }

  /* ─── Agent state integration ─────────────────────────────────── */

  setAgentState(state: AgentState): void {
    if (this._agentState === state) return;
    const prev = this._agentState;
    this._agentState = state;

    const behaviorId = AGENT_STATE_TO_BEHAVIOR[state];
    if (behaviorId) {
      this._abortCurrent();
      this._triggerById(behaviorId);
    } else if (prev !== 'IDLE') {
      // Returning to IDLE — abort event behavior, let scheduler resume
      this._abortCurrent();
      this._nextDecisionAt = performance.now() + 1_000;
    }
  }

  freeze(): void {
    this._abortCurrent();
    this.engine.freeze();
  }

  unfreeze(): void {
    this.engine.unfreeze();
    this._nextDecisionAt = performance.now() + 1_500;
  }

  /** Pause new ambient behaviors while allowing current movement to finish. */
  setBehaviorsSuspended(suspended: boolean): void {
    this._behaviorsSuspended = suspended;
    if (!suspended) this._nextDecisionAt = performance.now() + 1_500;
  }

  onPosition(callback: (position: PetPosition) => void): () => void {
    return this.engine.onPosition(callback);
  }

  /* ─── Drag relay ────────────────────────────────────────────────── */

  beginDrag(cx: number, cy: number): void {
    this._abortCurrent();
    this.engine.beginDrag(cx, cy);
  }

  dragTo(cx: number, cy: number): void {
    this.engine.dragTo(cx, cy);
  }

  endDrag(cx: number, cy: number): void {
    this.engine.endDrag(cx, cy);
    // After a hard throw, schedule dizzy-tumble once the pet lands
    const checkLanding = () => {
      if (this.engine.grounded) {
        const speed = Math.hypot(cx, cy); // rough proxy
        if (speed > 10) this._triggerById('dizzy-tumble');
        else this._nextDecisionAt = performance.now() + 1_500;
      } else {
        setTimeout(checkLanding, 80);
      }
    };
    setTimeout(checkLanding, 150);
  }

  /* ─── Private: rAF loop ─────────────────────────────────────────── */

  private _lastTickAt = 0;

  private _loop = (now: number): void => {
    if (!this._running) return;

    const isIdle = this.engine.isVisuallyIdle;
    // Active movement/drag: high-rate animation (~16ms).
    // Idle/sleeping: throttle ticks to ~100ms to keep CPU/GPU < 5%.
    if (!isIdle || now - this._lastTickAt >= 100) {
      this._lastTickAt = now;
      this.engine.tick(now);
      this._schedule(now);
    }

    this.rafId = requestAnimationFrame(this._loop);
  };

  private _schedule(now: number): void {
    if (this._behaviorsSuspended) return;
    // Only pick ambient behaviors when agent is IDLE and no behavior is running
    if (this._agentState !== 'IDLE') return;
    if (this.engine.isFrozen) return;
    if (this._currentBehavior !== null) return;
    if (now < this._nextDecisionAt) return;

    this._pickAndStart(now);
  }

  private _pickAndStart(now: number): void {
    const screenW = window.innerWidth;
    const ctx: BehaviorCtx = { engine: this.engine, signal: new AbortController().signal, screenW };

    const candidates: { def: BehaviorDef; weight: number }[] = [];
    for (const def of BEHAVIORS) {
      if (def.weight <= 0) continue;
      if ((this._cooldownUntil.get(def.id) ?? 0) > now) continue;
      if (!def.eligible(ctx)) continue;
      const w = def.weight * (this._recent.includes(def.id) ? 0.25 : 1);
      candidates.push({ def, weight: w });
    }
    if (!candidates.length) {
      this._nextDecisionAt = now + 1_500;
      return;
    }
    const total = candidates.reduce((s, c) => s + c.weight, 0);
    let roll = Math.random() * total;
    let chosen = candidates[candidates.length - 1].def;
    for (const c of candidates) {
      roll -= c.weight;
      if (roll <= 0) { chosen = c.def; break; }
    }
    this._startBehavior(chosen, now);
  }

  private _triggerById(id: string): void {
    const def = BEHAVIORS_BY_ID.get(id);
    if (!def) return;
    this._startBehavior(def, performance.now(), true);
  }

  private _startBehavior(def: BehaviorDef, now: number, isEvent = false): void {
    this._abortCurrent();
    const ctrl = new AbortController();
    this._currentCtrl = ctrl;
    this._currentBehavior = def.id;
    this._cooldownUntil.set(def.id, now + def.cooldownMs);
    this._pushRecent(def.id);

    const screenW = window.innerWidth;
    const ctx: BehaviorCtx = { engine: this.engine, signal: ctrl.signal, screenW };

    def.run(ctx)
      .catch(() => {})
      .finally(() => {
        if (this._currentBehavior === def.id) {
          this._currentBehavior = null;
          this._currentCtrl = null;
          this._nextDecisionAt = performance.now() + 1_200 + Math.random() * 2_000;
        }
      });
  }

  private _abortCurrent(): void {
    this._currentCtrl?.abort();
    this._currentCtrl = null;
    this._currentBehavior = null;
  }

  private _pushRecent(id: string): void {
    this._recent.push(id);
    if (this._recent.length > 4) this._recent.shift();
  }
}
