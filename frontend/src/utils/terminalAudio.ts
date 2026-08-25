let ctx: AudioContext | null = null;

function getAudioContext(): AudioContext | null {
  if (typeof window === 'undefined') {
    return null;
  }
  try {
    const Ctor =
      window.AudioContext || (window as Window & { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
    if (!Ctor) {
      return null;
    }
    if (!ctx) {
      ctx = new Ctor();
    }
    return ctx;
  } catch {
    ctx = null;
    return null;
  }
}

function beep(options: { frequency: number; durationMs: number; gain: number; type?: OscillatorType }) {
  try {
    const audio = getAudioContext();
    if (!audio) {
      return;
    }

    const osc = audio.createOscillator();
    const gain = audio.createGain();
    osc.type = options.type ?? 'square';
    osc.frequency.value = options.frequency;
    gain.gain.value = options.gain;

    osc.connect(gain);
    gain.connect(audio.destination);

    const now = audio.currentTime;
    const duration = options.durationMs / 1000;

    gain.gain.setValueAtTime(options.gain, now);
    gain.gain.exponentialRampToValueAtTime(0.0001, now + duration);

    osc.start(now);
    osc.stop(now + duration);
  } catch {
    // WebKit (and some headless browsers) reject AudioContext or ramps without a gesture.
  }
}

export function playKeyClick() {
  beep({ frequency: 980, durationMs: 18, gain: 0.02, type: 'square' });
}

export function playSendChirp() {
  beep({ frequency: 540, durationMs: 35, gain: 0.03, type: 'triangle' });
}
