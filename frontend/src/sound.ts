/**
 * Small sound-effect layer for the table.
 *
 * Everything here is synthesized with the Web Audio API — no audio
 * files to fetch, license, or bundle. Each effect is just a short
 * sequence of oscillator tones, which keeps this dependency-free and
 * trivial to tweak (change a frequency/duration, not a sample).
 *
 * Only "core moment" events get a sound (see Table.tsx's effect that
 * calls into this module): a card being played, a forced/voluntary
 * draw, your turn starting, and the game ending. Everything else
 * (skip, reverse, question asked, Niko Kadi, ...) stays silent for
 * now rather than turning the log into constant noise — see the
 * EventLog for the full blow-by-blow instead.
 */

const MUTE_KEY = "kenyan-poker:sound-muted";

let ctx: AudioContext | null = null;
let masterGain: GainNode | null = null;
let muted = readStoredMuted();

function readStoredMuted(): boolean {
  try {
    return window.localStorage.getItem(MUTE_KEY) === "1";
  } catch {
    // Storage can be unavailable (private mode, disabled cookies,
    // etc.) — default to unmuted rather than failing to load.
    return false;
  }
}

function writeStoredMuted(value: boolean): void {
  try {
    window.localStorage.setItem(MUTE_KEY, value ? "1" : "0");
  } catch {
    // Nothing to do if storage isn't available — the in-memory
    // `muted` flag still works for the rest of this session.
  }
}

export function isMuted(): boolean {
  return muted;
}

export function setMuted(value: boolean): void {
  muted = value;
  writeStoredMuted(value);

  if (masterGain) {
    masterGain.gain.value = value ? 0 : 1;
  }
}

export function toggleMuted(): boolean {
  setMuted(!muted);
  return muted;
}

// Lazily created — browsers refuse to start an AudioContext before a
// user gesture, and by the time any of the play*() functions below
// are called the player has already clicked/tapped their way into a
// game, so this is safe to create on first use rather than needing
// its own explicit "enable sound" button.
function getContext(): AudioContext | null {
  if (typeof window === "undefined") {
    return null;
  }

  const AudioContextCtor =
    window.AudioContext ||
    (window as unknown as { webkitAudioContext?: typeof AudioContext })
      .webkitAudioContext;

  if (!AudioContextCtor) {
    return null;
  }

  if (!ctx) {
    ctx = new AudioContextCtor();
    masterGain = ctx.createGain();
    masterGain.gain.value = muted ? 0 : 1;
    masterGain.connect(ctx.destination);
  }

  if (ctx.state === "suspended") {
    void ctx.resume();
  }

  return ctx;
}

interface ToneOptions {
  type?: OscillatorType;
  startTime?: number;
  duration?: number;
  peakGain?: number;
  frequencyEnd?: number;
}

// A single short tone with a quick attack and an exponential decay to
// (near) silence, so notes don't click or overlap into mush when
// several play close together (e.g. one blip per card in a multi-
// card draw).
function tone(
  audioCtx: AudioContext,
  destination: AudioNode,
  frequency: number,
  {
    type = "sine",
    startTime = 0,
    duration = 0.12,
    peakGain = 0.2,
    frequencyEnd,
  }: ToneOptions = {},
): void {
  const oscillator = audioCtx.createOscillator();
  const gain = audioCtx.createGain();

  oscillator.type = type;
  oscillator.frequency.setValueAtTime(frequency, startTime);

  if (frequencyEnd !== undefined) {
    oscillator.frequency.exponentialRampToValueAtTime(
      frequencyEnd,
      startTime + duration,
    );
  }

  gain.gain.setValueAtTime(0, startTime);
  gain.gain.linearRampToValueAtTime(peakGain, startTime + 0.008);
  gain.gain.exponentialRampToValueAtTime(0.0001, startTime + duration);

  oscillator.connect(gain);
  gain.connect(destination);

  oscillator.start(startTime);
  oscillator.stop(startTime + duration + 0.02);
}

function play(build: (audioCtx: AudioContext, destination: AudioNode) => void): void {
  if (muted) {
    return;
  }

  const audioCtx = getContext();
  if (!audioCtx || !masterGain) {
    return;
  }

  build(audioCtx, masterGain);
}

/** A card landing on the discard pile — a short, dry tick. */
export function playCardPlayed(): void {
  play((audioCtx, destination) => {
    const now = audioCtx.currentTime;
    tone(audioCtx, destination, 720, {
      type: "triangle",
      startTime: now,
      duration: 0.07,
      peakGain: 0.18,
      frequencyEnd: 500,
    });
  });
}

// Short burst of filtered noise — the raw material for a "whoosh".
// Built once per call (cheap: a handful of samples at typical
// durations) rather than cached, since each call needs its own
// buffer/source pair anyway (AudioBufferSourceNode is single-use).
function noiseSwoosh(
  audioCtx: AudioContext,
  destination: AudioNode,
  {
    startTime = 0,
    duration = 0.22,
    peakGain = 0.16,
    filterStart = 400,
    filterEnd = 2200,
  }: {
    startTime?: number;
    duration?: number;
    peakGain?: number;
    filterStart?: number;
    filterEnd?: number;
  } = {},
): void {
  const sampleCount = Math.max(1, Math.floor(audioCtx.sampleRate * duration));
  const buffer = audioCtx.createBuffer(1, sampleCount, audioCtx.sampleRate);
  const data = buffer.getChannelData(0);

  for (let i = 0; i < sampleCount; i += 1) {
    data[i] = Math.random() * 2 - 1;
  }

  const source = audioCtx.createBufferSource();
  source.buffer = buffer;

  const filter = audioCtx.createBiquadFilter();
  filter.type = "bandpass";
  filter.Q.value = 0.7;
  filter.frequency.setValueAtTime(filterStart, startTime);
  filter.frequency.exponentialRampToValueAtTime(filterEnd, startTime + duration);

  const gain = audioCtx.createGain();
  gain.gain.setValueAtTime(0, startTime);
  gain.gain.linearRampToValueAtTime(peakGain, startTime + duration * 0.3);
  gain.gain.exponentialRampToValueAtTime(0.0001, startTime + duration);

  source.connect(filter);
  filter.connect(gain);
  gain.connect(destination);

  source.start(startTime);
  source.stop(startTime + duration + 0.02);
}

/**
 * A normal, voluntary single-card draw (or a failed-question draw) —
 * a quick airy whoosh, distinct from the punishment sound below.
 */
export function playNormalDraw(): void {
  play((audioCtx, destination) => {
    noiseSwoosh(audioCtx, destination, {
      startTime: audioCtx.currentTime,
      duration: 0.2,
      peakGain: 0.16,
      filterStart: 500,
      filterEnd: 2400,
    });
  });
}

/**
 * A punishment draw landing — a player was forced to draw for
 * unavoidable draw pressure. Two short descending "wup wup" tones so
 * it reads as a distinct, slightly comic penalty rather than the
 * plain whoosh of a normal draw.
 */
export function playPunishmentDraw(): void {
  play((audioCtx, destination) => {
    const now = audioCtx.currentTime;

    tone(audioCtx, destination, 220, {
      type: "square",
      startTime: now,
      duration: 0.11,
      peakGain: 0.16,
      frequencyEnd: 140,
    });
    tone(audioCtx, destination, 200, {
      type: "square",
      startTime: now + 0.13,
      duration: 0.13,
      peakGain: 0.16,
      frequencyEnd: 120,
    });
  });
}

/** A gentle two-note chime when it becomes your turn. */
export function playYourTurn(): void {
  play((audioCtx, destination) => {
    const now = audioCtx.currentTime;
    tone(audioCtx, destination, 523.25, {
      // C5
      type: "sine",
      startTime: now,
      duration: 0.14,
      peakGain: 0.16,
    });
    tone(audioCtx, destination, 783.99, {
      // G5
      type: "sine",
      startTime: now + 0.1,
      duration: 0.18,
      peakGain: 0.16,
    });
  });
}

/** A short rising arpeggio for a win. */
export function playWin(): void {
  play((audioCtx, destination) => {
    const now = audioCtx.currentTime;
    const notes = [523.25, 659.25, 783.99, 1046.5]; // C5 E5 G5 C6

    notes.forEach((frequency, index) => {
      tone(audioCtx, destination, frequency, {
        type: "triangle",
        startTime: now + index * 0.09,
        duration: 0.22,
        peakGain: 0.18,
      });
    });
  });
}

/** A short falling pair for a loss — deliberately understated. */
export function playLose(): void {
  play((audioCtx, destination) => {
    const now = audioCtx.currentTime;
    tone(audioCtx, destination, 392, {
      // G4
      type: "sine",
      startTime: now,
      duration: 0.22,
      peakGain: 0.14,
    });
    tone(audioCtx, destination, 293.66, {
      // D4
      type: "sine",
      startTime: now + 0.16,
      duration: 0.3,
      peakGain: 0.14,
    });
  });
}
