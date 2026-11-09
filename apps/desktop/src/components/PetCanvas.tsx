import React, { useEffect, useRef, useState } from 'react';
import { Sparkles } from 'lucide-react';

export type PetState = 'IDLE' | 'THINKING' | 'ANALYZING' | 'WORKING' | 'BROWSING' | 'ERROR';

interface PetCanvasProps {
  state: PetState;
  onClick: () => void;
  statusMessage?: string;
}

export const PetCanvas: React.FC<PetCanvasProps> = ({ state, onClick, statusMessage }) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [frame, setFrame] = useState(0);
  const [customPetSrc, setCustomPetSrc] = useState<string | null>(null);

  // Drag state (widget behavior)
  const [pos, setPos] = useState({ x: 0, y: 0 });
  const [dragging, setDragging] = useState(false);
  const [dragOffset, setDragOffset] = useState({ x: 0, y: 0 });

  // Load possible custom pet image
  useEffect(() => {
    const candidatePaths = ['/src/assets/pet.webp', '/src/assets/pet.gif', '/src/assets/pet.png'];
    let mounted = true;
    const checkNext = (idx: number) => {
      if (idx >= candidatePaths.length || !mounted) return;
      const img = new Image();
      img.onload = () => { if (mounted) setCustomPetSrc(candidatePaths[idx]); };
      img.onerror = () => checkNext(idx + 1);
      img.src = candidatePaths[idx];
    };
    checkNext(0);
    return () => { mounted = false; };
  }, []);

  // Simple frame timer for pixel animation
  useEffect(() => {
    const timer = setInterval(() => setFrame(f => (f + 1) % 100), 110);
    return () => clearInterval(timer);
  }, []);

  // Canvas drawing (fallback when no custom image)
  useEffect(() => {
    if (customPetSrc) return;
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    const pixelSize = 4;
    const offsetX = 16;
    const offsetY = 12;
    const p = (x: number, y: number, color: string) => {
      ctx.fillStyle = color;
      ctx.fillRect((offsetX + x) * pixelSize, (offsetY + y) * pixelSize, pixelSize, pixelSize);
    };
    const WHITE = '#FFFFFF';
    const LIGHT_GRAY = '#E5E7EB';
    const SHADOW = '#D1D5DB';
    const NOSE = '#1F2937';
    const COLLAR = '#EF4444';
    const TAG = '#F59E0B';
    // Eye colour per state
    let eyeColor = '#111827';
    if (state === 'THINKING') eyeColor = '#3B82F6';
    if (state === 'ANALYZING') eyeColor = '#8B5CF6';
    if (state === 'WORKING') eyeColor = '#10B981';
    if (state === 'BROWSING') eyeColor = '#06B6D4';
    if (state === 'ERROR') eyeColor = '#EF4444';
    const tailWag = (state === 'IDLE' || state === 'BROWSING') ? (frame % 2 === 0 ? 0 : 1) : 0;
    const earBounce = (state === 'THINKING' || state === 'WORKING') ? (frame % 2 === 0 ? -1 : 0) : 0;
    const pawMove = state === 'WORKING' ? (frame % 2 === 0 ? 1 : 0) : 0;
    // Tail
    p(1 + tailWag, 8, SHADOW);
    p(2 + tailWag, 7, WHITE);
    p(2 + tailWag, 6, WHITE);
    // Body
    for (let x = 3; x <= 10; x++) for (let y = 8; y <= 12; y++) p(x, y, WHITE);
    for (let x = 3; x <= 10; x++) p(x, 13, SHADOW);
    // Legs / paws
    p(3, 14, SHADOW); p(4, 14 - pawMove, WHITE);
    p(6, 14, SHADOW); p(7, 14 + pawMove, WHITE);
    p(9, 14, SHADOW); p(10, 14, WHITE);
    // Collar & tag
    for (let x = 9; x <= 12; x++) p(x, 7, COLLAR);
    p(11, 8, TAG);
    // Head
    for (let x = 9; x <= 15; x++) for (let y = 2 + earBounce; y <= 6 + earBounce; y++) p(x, y, WHITE);
    // Ears
    p(9, 1 + earBounce, LIGHT_GRAY); p(10, 1 + earBounce, LIGHT_GRAY);
    p(14, 1 + earBounce, LIGHT_GRAY); p(15, 1 + earBounce, LIGHT_GRAY);
    // Snout & nose
    p(15, 5 + earBounce, SHADOW);
    p(16, 5 + earBounce, NOSE);
    // Eyes / glasses
    if (state === 'BROWSING') {
      p(11, 3 + earBounce, '#06B6D4');
      p(12, 3 + earBounce, '#06B6D4');
      p(13, 3 + earBounce, '#06B6D4');
      p(14, 3 + earBounce, '#06B6D4');
    } else if (state === 'THINKING' && frame % 4 < 2) {
      p(12, 4 + earBounce, eyeColor);
      p(13, 4 + earBounce, eyeColor);
    } else {
      p(12, 3 + earBounce, eyeColor);
      p(13, 3 + earBounce, eyeColor);
      p(12, 4 + earBounce, eyeColor);
    }
    if ((state === 'WORKING' || state === 'ANALYZING') && frame % 2 === 0) {
      p(16, 1 + earBounce, eyeColor);
    }
  }, [frame, state, customPetSrc]);

  const getStateEffects = () => {
    switch (state) {
      case 'THINKING':
        return 'animate-pulse drop-shadow-[0_0_20px_rgba(59,130,246,0.6)] border-blue-500/50';
      case 'ANALYZING':
        return 'animate-pulse drop-shadow-[0_0_22px_rgba(139,92,246,0.7)] border-purple-500/50';
      case 'WORKING':
        return 'animate-bounce drop-shadow-[0_0_25px_rgba(16,185,129,0.7)] border-emerald-500/50';
      case 'BROWSING':
        return 'animate-pulse drop-shadow-[0_0_20px_rgba(6,182,212,0.7)] border-cyan-500/50';
      case 'ERROR':
        return 'drop-shadow-[0_0_20px_rgba(239,68,68,0.8)] border-rose-500/50';
      default:
        return 'hover:translate-y-[-2px] transition-transform duration-300 drop-shadow-[0_10px_20px_rgba(0,0,0,0.5)]';
    }
  };

  const defaultSpeech = {
    IDLE: 'Woof! Click me to open Johnny Console!',
    THINKING: 'Thinking with LLM ensemble...',
    ANALYZING: 'Analyzing screen & vision...',
    WORKING: 'Executing task & tools...',
    BROWSING: 'Browsing web pages securely...',
    ERROR: 'Ouch! Check console logs.',
  }[state];
  const speechText = statusMessage || defaultSpeech;

  // Drag handlers
  const handleMouseDown = (e: React.MouseEvent) => {
    setDragOffset({ x: e.clientX - pos.x, y: e.clientY - pos.y });
    setDragging(true);
  };
  const handleMouseMove = (e: MouseEvent) => {
    if (!dragging) return;
    setPos({ x: e.clientX - dragOffset.x, y: e.clientY - dragOffset.y });
  };
  const handleMouseUp = () => setDragging(false);
  useEffect(() => {
    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseup', handleMouseUp);
    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };
  }, [dragging, dragOffset]);

  return (
    <div className="group relative flex flex-col items-end cursor-pointer select-none">
      {/* Speech bubble */}
      <div className="mb-2 max-w-[260px] rounded-xl bg-slate-950/95 border border-slate-700/80 p-2.5 text-xs text-slate-100 shadow-2xl backdrop-blur-md transition-all duration-200 group-hover:scale-105 border-indigo-500/30">
        <div className="flex items-center justify-between gap-1.5 font-semibold text-slate-200">
          <div className="flex items-center gap-1.5">
            <Sparkles className="h-3.5 w-3.5 text-amber-400 animate-pulse" />
            <span className="text-slate-200 font-bold">Johnny Deskmate</span>
          </div>
          <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-slate-800 text-indigo-300 border border-slate-700">
            {state === 'THINKING' ? 'Llama 70B' : state === 'ANALYZING' ? 'MiniMax M3' : state === 'BROWSING' ? 'Playwright' : 'V1.1 Agent'}
          </span>
        </div>
        <p className="mt-1 text-[11px] text-slate-300 leading-snug font-sans">{speechText}</p>
      </div>

      {/* Draggable pet widget */}
      <div
        style={{
          transform: `translate3d(${pos.x}px, ${pos.y}px, 0)`,
          cursor: dragging ? 'grabbing' : 'grab'
        }}
        onMouseDown={handleMouseDown}
        onClick={onClick}
        className={`relative p-2 transition-transform duration-100 hover:scale-105 active:scale-95 select-none ${getStateEffects()}`}
        title="Click to toggle Johnny Console (Drag to move pet)"
      >
        {/* State glow badge */}
        <div className="absolute -top-1 -right-1 z-10 flex items-center gap-1 rounded-full bg-slate-900/95 px-2 py-0.5 text-[10px] font-semibold text-slate-200 border border-slate-700 shadow-lg backdrop-blur-sm">
          <span className={`h-2 w-2 rounded-full ${
            state === 'IDLE' ? 'bg-emerald-400 animate-pulse' :
            state === 'THINKING' ? 'bg-blue-400 animate-spin' :
            state === 'ANALYZING' ? 'bg-purple-400 animate-ping' :
            state === 'WORKING' ? 'bg-emerald-500 animate-bounce' :
            state === 'BROWSING' ? 'bg-cyan-400 animate-pulse' :
            'bg-rose-500'
          }`} />
          {state}
        </div>
        {customPetSrc ? (
          <img
            src={customPetSrc}
            alt="Johnny Custom Pet"
            draggable={false}
            className="w-[120px] h-[100px] object-contain drop-shadow-[0_12px_20px_rgba(0,0,0,0.7)] [image-rendering:pixelated] pointer-events-none select-none"
          />
        ) : (
          <canvas ref={canvasRef} width={110} height={90} className="drop-shadow-[0_10px_15px_rgba(0,0,0,0.6)]" />
        )}
      </div>
    </div>
  );
};
