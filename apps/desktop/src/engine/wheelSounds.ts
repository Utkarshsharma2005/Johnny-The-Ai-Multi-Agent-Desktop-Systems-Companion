const STORAGE_KEY = 'johnny_wheel_sounds';

type WheelCue = 'open' | 'close' | 'hover' | 'select';

const tones: Record<WheelCue, Array<[number, number, number, number]>> = {
  open: [[523.25, 0, 0.13, 0.13], [783.99, 0.05, 0.16, 0.1]],
  close: [[783.99, 0, 0.11, 0.1], [523.25, 0.04, 0.14, 0.09]],
  hover: [[880, 0, 0.035, 0.035]],
  select: [[659.25, 0, 0.08, 0.11], [987.77, 0.04, 0.12, 0.08]],
};

let context: AudioContext | null = null;
let lastHoverAt = 0;

export function isWheelSoundEnabled(): boolean {
  return localStorage.getItem(STORAGE_KEY) !== 'false';
}

export function setWheelSoundEnabled(enabled: boolean): void {
  localStorage.setItem(STORAGE_KEY, String(enabled));
}

export function playWheelSound(cue: WheelCue): void {
  if (!isWheelSoundEnabled()) return;
  if (cue === 'hover') {
    const now = performance.now();
    if (now - lastHoverAt < 80) return;
    lastHoverAt = now;
  }

  try {
    context ??= new AudioContext();
    if (context.state === 'suspended') void context.resume();
    const start = context.currentTime + 0.01;
    for (const [frequency, offset, duration, volume] of tones[cue]) {
      const oscillator = context.createOscillator();
      const gain = context.createGain();
      const at = start + offset;
      oscillator.type = 'sine';
      oscillator.frequency.setValueAtTime(frequency, at);
      gain.gain.setValueAtTime(0.0001, at);
      gain.gain.exponentialRampToValueAtTime(volume * 0.18, at + 0.012);
      gain.gain.exponentialRampToValueAtTime(0.0001, at + duration);
      oscillator.connect(gain).connect(context.destination);
      oscillator.start(at);
      oscillator.stop(at + duration + 0.01);
    }
  } catch {
    // UI audio should never interrupt wheel actions.
  }
}
