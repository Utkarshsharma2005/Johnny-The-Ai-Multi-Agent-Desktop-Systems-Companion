/**
 * PetEngine.ts — Johnny's physics-driven pet movement engine.
 *
 * Authentic Shimeji physics & frame orchestration:
 *   - 60 FPS rAF imperative loop writing directly to DOM transform.
 *   - Gravity = 0.10 px/step², Damping = 0.98, Bounce = 0.38.
 *   - Multi-state frame sequencing (walking, falling, landing bounce, climbing,
 *     idle, sleeping with "zzz", thinking/working with glowing aura).
 *   - Real sprite assets from /assets/<character>/ (walk1..3, fall1..5, drag1..3, id1..2, sp1..3).
 *   - Throw physics with momentum & wall bounces.
 */

export type PetPhysicsState =
  | 'idle'
  | 'walking'
  | 'falling'
  | 'dragging'
  | 'sleeping'
  | 'thinking'
  | 'working'
  | 'error'
  | 'celebrating'
  | 'dizzy';

export interface PetEngineConfig {
  /** Logical pixels; pet is a square (e.g. 100). */
  size: number;
  /** Character asset folder name under /assets/ (e.g. 'spongebob', 'deadpool', 'klee', 'albedo'). */
  character?: string;
  /** Gravity acceleration per step (px/step²). */
  gravity?: number;
  /** Velocity decay multiplier per step (0–1). */
  damping?: number;
  /** Floor restitution coefficient (0 = no bounce, 1 = perfect bounce). */
  bounce?: number;
  /** Callback fired when the agent state changes. */
  onStateChange?: (state: PetPhysicsState) => void;
}

export interface PetPosition {
  x: number;
  y: number;
  size: number;
}

const GRAVITY = 0.10;
const DAMPING = 0.98;
const BOUNCE  = 0.38;
const THROW_SPEED_DIZZY = 18;

export class PetEngine {
  private el: HTMLElement | null = null;
  private imgEl: HTMLImageElement | null = null;
  private x = 100;
  private y = 100;
  private vx = 0;
  private vy = 0;
  private floorY = 0;
  private _state: PetPhysicsState = 'idle';
  private _dragging = false;
  private _dragOffsetX = 0;
  private _dragOffsetY = 0;
  private _lastDragX = 0;
  private _lastDragY = 0;
  private _walkTarget: number | null = null;
  private _walkResolve: ((reached: boolean) => void) | null = null;
  private _grounded = false;
  private _face: 'left' | 'right' = 'right';
  private _frame = 0;
  private _lastFrameAt = 0;
  private _frameMs = 120; // animation frame interval (120ms)
  private _character = 'spongebob';
  private _landingFrame = 0;
  private _landingTimer = 0;
  private _lastWrittenX = -99999;
  private _lastWrittenY = -99999;
  private _positionListeners = new Set<(position: PetPosition) => void>();

  private _cfg: Required<PetEngineConfig>;
  private _onStateChange?: (s: PetPhysicsState) => void;

  constructor(cfg: PetEngineConfig) {
    this._character = cfg.character || 'spongebob';
    this._cfg = {
      size: cfg.size,
      character: this._character,
      gravity: cfg.gravity ?? GRAVITY,
      damping: cfg.damping ?? DAMPING,
      bounce:  cfg.bounce  ?? BOUNCE,
      onStateChange: cfg.onStateChange ?? (() => {}),
    };
    this._onStateChange = cfg.onStateChange;
  }

  /* ─── Public API ─────────────────────────────────────────────── */

  /** Register the DOM element the engine will move. */
  register(el: HTMLElement): void {
    this.el = el;
    this.imgEl = el.querySelector<HTMLImageElement>('.pet-sprite-img') ?? el.querySelector<HTMLImageElement>('img');
    // Start near bottom-right of viewport
    this.floorY = window.innerHeight - this._cfg.size - 14;
    this.x = window.innerWidth - this._cfg.size - 24;
    this.y = this.floorY;
    this._grounded = true;
    this._writeTransform();
    window.addEventListener('resize', this._onResize);
  }

  unregister(): void {
    window.removeEventListener('resize', this._onResize);
    this.el = null;
    this.imgEl = null;
  }

  onPosition(callback: (position: PetPosition) => void): () => void {
    this._positionListeners.add(callback);
    callback({ x: this.x, y: this.y, size: this._cfg.size });
    return () => this._positionListeners.delete(callback);
  }

  setCharacter(charName: string): void {
    this._character = charName;
    this._cfg.character = charName;
    this._updateSpriteFrame();
  }

  private _frozen = false;

  freeze(): void {
    this._frozen = true;
    this.vx = 0;
    this.vy = 0;
    this._walkTarget = null;
    this.y = this.floorY;
    this._grounded = true;
    this._setState('idle');
    this._writeTransform();
  }

  unfreeze(): void {
    this._frozen = false;
  }

  get isFrozen(): boolean {
    return this._frozen;
  }

  /** Main physics step — called every rAF frame from Director. */
  tick(now: number): void {
    if (!this.el || this._dragging) return;

    if (this._frozen) {
      if (now - this._lastFrameAt > this._frameMs) {
        this._frame++;
        this._lastFrameAt = now;
        this._updateSpriteFrame();
      }
      return;
    }

    // ── Animation frame counter (throttled at _frameMs) ──────────
    if (now - this._lastFrameAt > this._frameMs) {
      this._frame++;
      this._lastFrameAt = now;
      this._updateSpriteFrame();
    }

    // ── Physics step ──────────────────────────────────────────────
    if (!this._grounded) {
      this.vy += this._cfg.gravity;
    }
    this.vx *= this._cfg.damping;
    this.vy *= this._cfg.damping;

    this.x += this.vx;
    this.y += this.vy;

    // ── Floor collision ───────────────────────────────────────────
    const floor = this.floorY;
    if (this.y >= floor) {
      this.y = floor;
      if (!this._grounded) {
        // Landing impact
        if (Math.abs(this.vy) > 2) {
          this.vy = -this.vy * this._cfg.bounce;
          this._startLandingSequence();
        } else {
          this.vy = 0;
          this._grounded = true;
          this._startLandingSequence();
        }
      }
    } else {
      this._grounded = false;
    }

    // ── Wall collision & horizontal margin ─────────────────────────
    // Margin of 140px ensures the attached skill wheel (R=125px)
    // is never clipped by left or right edges of the screen.
    const margin = 140;
    const maxX = Math.max(margin + 50, window.innerWidth - this._cfg.size - margin);
    if (this.x < margin) {
      this.x = margin;
      this.vx = Math.abs(this.vx) * 0.45;
      this._face = 'right';
    } else if (this.x > maxX) {
      this.x = maxX;
      this.vx = -Math.abs(this.vx) * 0.45;
      this._face = 'left';
    }

    // Keep grounded pet strictly at floor level (no accidental vertical jump)
    if (this._grounded) {
      this.y = this.floorY;
      this.vy = 0;
    }

    // ── Walk-to target logic ──────────────────────────────────────
    if (this._walkTarget !== null && this._grounded) {
      const dx = this._walkTarget - this.x;
      if (Math.abs(dx) < 3) {
        this.x = this._walkTarget;
        this.vx = 0;
        this._walkTarget = null;
        this._setState('idle');
        this._walkResolve?.(true);
        this._walkResolve = null;
      } else {
        const speed = Math.min(Math.max(Math.abs(dx) * 0.06, 1.2), 3.2);
        this.vx = dx > 0 ? speed : -speed;
        this._face = dx > 0 ? 'right' : 'left';
        this._setState('walking');
      }
    }

    this._writeTransform();
  }

  /* ─── Drag API ────────────────────────────────────────────────── */

  beginDrag(clientX: number, clientY: number): void {
    this._dragging = true;
    this._dragOffsetX = clientX - this.x;
    this._dragOffsetY = clientY - this.y;
    this._lastDragX = clientX;
    this._lastDragY = clientY;
    this._walkTarget = null;
    this._walkResolve?.(false);
    this._walkResolve = null;
    this._setState('dragging');
    this.el?.setAttribute('data-dragging', 'true');
    this._updateSpriteFrame();
  }

  dragTo(clientX: number, clientY: number): void {
    if (!this._dragging) return;
    this._lastDragX = clientX;
    this._lastDragY = clientY;
    this.x = clientX - this._dragOffsetX;
    this.y = clientY - this._dragOffsetY;
    this._writeTransform();
  }

  endDrag(clientX: number, clientY: number): void {
    if (!this._dragging) return;
    this._dragging = false;
    this.el?.setAttribute('data-dragging', 'false');
    // Compute throw velocity
    this.vx = (clientX - this._lastDragX) * 0.55;
    this.vy = (clientY - this._lastDragY) * 0.55;
    const speed = Math.sqrt(this.vx * this.vx + this.vy * this.vy);
    this._grounded = false;

    if (speed > THROW_SPEED_DIZZY) {
      this._setState('dizzy');
    } else {
      this._setState('falling');
    }
    this._updateSpriteFrame();
  }

  /* ─── Behavior API ────────────────────────────────────────────── */

  walkTo(targetX: number): Promise<boolean> {
    return new Promise<boolean>((resolve) => {
      this._walkResolve?.(false);
      this._walkTarget = Math.max(0, Math.min(targetX, window.innerWidth - this._cfg.size));
      this._walkResolve = resolve;
    });
  }

  teleport(x: number, y: number): void {
    this.x = x;
    this.y = y;
    this.vx = 0;
    this.vy = 0;
    this._grounded = y >= this.floorY - 2;
    this._writeTransform();
  }

  setAgentState(state: PetPhysicsState): void {
    if (this._dragging || this._state === 'dragging') return;
    if (!this._grounded && state !== 'falling') return;
    this._setState(state);
    this._updateSpriteFrame();
  }

  face(dir: 'left' | 'right'): void {
    this._face = dir;
    this._updateSpriteFrame();
  }

  get state(): PetPhysicsState { return this._state; }
  get grounded(): boolean      { return this._grounded; }
  get posX(): number           { return this.x; }
  get posY(): number           { return this.y; }
  get frame(): number          { return this._frame; }
  get character(): string      { return this._character; }

  get isVisuallyIdle(): boolean {
    return (
      this._grounded &&
      this._walkTarget === null &&
      Math.abs(this.vx) < 0.05 &&
      Math.abs(this.vy) < 0.05 &&
      !this._dragging &&
      (this._state === 'idle' || this._state === 'sleeping')
    );
  }

  /* ─── Private Methods ──────────────────────────────────────────── */

  private _setState(s: PetPhysicsState): void {
    if (this._state === s) return;
    this._state = s;
    this._onStateChange?.(s);
    if (this.el) {
      this.el.setAttribute('data-state', this._state);
      this.el.setAttribute('data-face', this._face);
    }
  }

  private _startLandingSequence(): void {
    this._landingFrame = 2; // bounce frame
    this._setState('falling');
    this._updateSpriteFrame();
    window.clearTimeout(this._landingTimer);
    this._landingTimer = window.setTimeout(() => {
      this._landingFrame = 4; // settle frame
      this._updateSpriteFrame();
      this._landingTimer = window.setTimeout(() => {
        this._landingFrame = 0;
        this._grounded = true;
        this._setState('idle');
        this._updateSpriteFrame();
      }, 250);
    }, 140);
  }

  /** Calculate current frame path based on state and animation tick. */
  private _getFrameSrc(): string {
    const base = `/assets/${this._character}`;
    switch (this._state) {
      case 'dragging':
        return `${base}/drag1.png`;

      case 'falling':
        if (this._landingFrame > 0) {
          return `${base}/fall${this._landingFrame}.png`;
        }
        return `${base}/fall1.png`;

      case 'walking': {
        const walkCycle = ['walk1', 'walk2', 'walk3', 'walk2'];
        const frameName = walkCycle[this._frame % walkCycle.length];
        return `${base}/${frameName}.png`;
      }

      case 'sleeping':
        return `${base}/id2_1.png`;

      case 'thinking': {
        const thinkCycle = ['sp1_1', 'sp1_2', 'sp1_3', 'sp1_2'];
        const f = thinkCycle[this._frame % thinkCycle.length];
        return `${base}/${f}.png`;
      }

      case 'working': {
        const workCycle = ['sp1_2', 'sp1_3', 'sp2_1', 'sp2_2'];
        const f = workCycle[this._frame % workCycle.length];
        return `${base}/${f}.png`;
      }

      case 'celebrating':
        return `${base}/sp1_1.png`;

      case 'dizzy':
        return `${base}/fall4.png`;

      case 'idle':
      default:
        return this._frame % 6 === 0 ? `${base}/id2_1.png` : `${base}/id1_1.png`;
    }
  }

  private _updateSpriteFrame(): void {
    if (!this.imgEl || !this.imgEl.isConnected) {
      this.imgEl = this.el?.querySelector<HTMLImageElement>('.pet-sprite-img') ?? this.el?.querySelector<HTMLImageElement>('img') ?? null;
    }
    if (this.imgEl) {
      const src = this._getFrameSrc();
      if (!this.imgEl.src.endsWith(src)) {
        this.imgEl.src = src;
      }
      // Shimeji convention: native sprites face LEFT.
      // If facing right, mirror with scaleX(-1).
      this.imgEl.style.transform = this._face === 'right' ? 'scaleX(-1)' : 'scaleX(1)';
    }
  }

  private _writeTransform(): void {
    if (!this.el) return;
    const rx = Math.round(this.x * 2) / 2;
    const ry = Math.round(this.y * 2) / 2;
    if (rx === this._lastWrittenX && ry === this._lastWrittenY) return;
    this._lastWrittenX = rx;
    this._lastWrittenY = ry;
    this.el.style.transform = `translate3d(${rx}px, ${ry}px, 0)`;
    const position = { x: rx, y: ry, size: this._cfg.size };
    this._positionListeners.forEach((listener) => listener(position));
  }

  private _onResize = (): void => {
    this.floorY = window.innerHeight - this._cfg.size - 14;
    if (this._grounded) {
      this.y = this.floorY;
      this._writeTransform();
    }
    const maxX = window.innerWidth - this._cfg.size;
    if (this.x > maxX) {
      this.x = maxX;
      this._writeTransform();
    }
  };
}
