/**
 * behaviors.ts — Johnny's behavior catalog.
 *
 * Each BehaviorDef describes a weighted ambient behavior that the
 * BehaviorDirector picks from when Johnny is idle.  Agent-driven
 * behaviors (thinking, working, error) are "event" behaviors with
 * weight=0 — they are only triggered externally, never picked by
 * the weighted scheduler.
 *
 * Structure mirrors the reference repo so porting new behaviors is
 * trivial: {id, weight, cooldownMs, eligible, run}.
 */

import type { PetEngine } from './PetEngine';

export interface BehaviorCtx {
  engine: PetEngine;
  signal: AbortSignal;
  screenW: number;
  data?: unknown;
}

export interface BehaviorDef {
  id: string;
  /** Sampling weight (0 = event-only, not sampled by scheduler). */
  weight: number;
  /** Minimum ms between two starts of the same behavior. */
  cooldownMs: number;
  /** Whether the behavior can start right now. */
  eligible: (ctx: BehaviorCtx) => boolean;
  /** The async behavior body. Must respect ctx.signal. */
  run: (ctx: BehaviorCtx) => Promise<void>;
}

/* ─── Tiny utilities ─────────────────────────────────────────────── */

export const wait = (ms: number, signal?: AbortSignal): Promise<void> =>
  new Promise<void>((resolve, reject) => {
    if (signal?.aborted) return reject(new DOMException('Aborted', 'AbortError'));
    const id = setTimeout(resolve, ms);
    signal?.addEventListener('abort', () => { clearTimeout(id); reject(new DOMException('Aborted', 'AbortError')); }, { once: true });
  });

const rand = (min: number, max: number) => min + Math.random() * (max - min);

/* ─── Behavior Definitions ───────────────────────────────────────── */

export const BEHAVIORS: BehaviorDef[] = [

  /* ── Ambient: wander walk ──────────────────────────────────────── */
  {
    id: 'wander-walk',
    weight: 3.0,
    cooldownMs: 4_000,
    eligible: (ctx) => ctx.engine.grounded && ctx.engine.state !== 'dragging',
    async run({ engine, signal, screenW }) {
      const margin = 80;
      const target = rand(margin, screenW - margin - 96);
      await engine.walkTo(target);
      await wait(rand(800, 2_500), signal);
    },
  },

  /* ── Ambient: idle sit ─────────────────────────────────────────── */
  {
    id: 'idle-sit',
    weight: 2.0,
    cooldownMs: 3_000,
    eligible: (ctx) => ctx.engine.grounded,
    async run({ engine, signal }) {
      engine.setAgentState('idle');
      await wait(rand(2_500, 5_000), signal);
    },
  },

  /* ── Ambient: short nap ────────────────────────────────────────── */
  {
    id: 'short-nap',
    weight: 0.8,
    cooldownMs: 30_000,
    eligible: (ctx) => ctx.engine.grounded,
    async run({ engine, signal }) {
      engine.setAgentState('sleeping');
      await wait(rand(4_000, 8_000), signal);
      engine.setAgentState('idle');
      await wait(500, signal);
    },
  },

  /* ── Ambient: edge peek (walk to edge and look off screen) ─────── */
  {
    id: 'edge-peek',
    weight: 0.6,
    cooldownMs: 20_000,
    eligible: (ctx) => ctx.engine.grounded,
    async run({ engine, signal, screenW }) {
      const goRight = Math.random() > 0.5;
      const target  = goRight ? screenW - 96 - 4 : 4;
      await engine.walkTo(target);
      engine.face(goRight ? 'right' : 'left');
      await wait(rand(1_200, 2_500), signal);
    },
  },

  /* ── Ambient: curious wiggle ───────────────────────────────────── */
  {
    id: 'curious-wiggle',
    weight: 0.5,
    cooldownMs: 8_000,
    eligible: (ctx) => ctx.engine.grounded && ctx.engine.state === 'idle',
    async run({ engine, signal }) {
      // Small shimmy: walk 15px left then right then back
      const base = engine.posX;
      engine.face('left');
      await wait(120, signal);
      await engine.walkTo(base - 15);
      await wait(120, signal);
      engine.face('right');
      await engine.walkTo(base + 15);
      await wait(120, signal);
      await engine.walkTo(base);
      await wait(600, signal);
    },
  },

  /* ── EVENT: thinking (triggered by agent THINKING state) ────────── */
  {
    id: 'agent-thinking',
    weight: 0,
    cooldownMs: 0,
    eligible: () => true,
    async run({ engine, signal }) {
      engine.setAgentState('thinking');
      // The Director will abort this when the agent state changes
      await new Promise<void>((_, reject) => {
        signal.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')), { once: true });
      });
    },
  },

  /* ── EVENT: working (triggered by agent WORKING/tool execution) ─── */
  {
    id: 'agent-working',
    weight: 0,
    cooldownMs: 0,
    eligible: () => true,
    async run({ engine, signal }) {
      engine.setAgentState('working');
      // Pace back and forth while working
      const base = engine.posX;
      let i = 0;
      while (!signal.aborted) {
        const offset = (i % 2 === 0) ? 20 : -20;
        if (engine.grounded) {
          const ok = await engine.walkTo(base + offset);
          if (!ok) break;
        }
        await wait(600, signal);
        i++;
      }
    },
  },

  /* ── EVENT: task success (jump + celebrate) ─────────────────────── */
  {
    id: 'task-success-jump',
    weight: 0,
    cooldownMs: 0,
    eligible: () => true,
    async run({ engine, signal }) {
      engine.setAgentState('celebrating');
      // Tiny jump: add upward velocity via teleport trick
      if (engine.grounded) {
        // We don't expose velocity directly, so simulate via walkTo quickly
        const base = engine.posX;
        await engine.walkTo(base + 10);
        await wait(80, signal);
        await engine.walkTo(base - 10);
        await wait(80, signal);
        await engine.walkTo(base);
      }
      await wait(1_800, signal);
      engine.setAgentState('idle');
    },
  },

  /* ── EVENT: error ear-droop ─────────────────────────────────────── */
  {
    id: 'error-ear-droop',
    weight: 0,
    cooldownMs: 0,
    eligible: () => true,
    async run({ engine, signal }) {
      engine.setAgentState('error');
      await wait(3_000, signal);
      engine.setAgentState('idle');
    },
  },

  /* ── EVENT: dizzy tumble (after hard throw) ─────────────────────── */
  {
    id: 'dizzy-tumble',
    weight: 0,
    cooldownMs: 0,
    eligible: () => true,
    async run({ engine, signal }) {
      engine.setAgentState('dizzy');
      await wait(rand(1_500, 2_500), signal);
      engine.setAgentState('idle');
    },
  },

];

export const BEHAVIORS_BY_ID = new Map(BEHAVIORS.map((b) => [b.id, b]));
