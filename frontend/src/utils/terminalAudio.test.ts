import { afterEach, describe, expect, it, vi } from 'vitest';
import { playKeyClick, playSendChirp } from './terminalAudio';

describe('terminalAudio', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('does not throw when AudioContext construction fails', () => {
    vi.stubGlobal(
      'AudioContext',
      class {
        constructor() {
          throw new Error('not allowed');
        }
      },
    );
    expect(() => playKeyClick()).not.toThrow();
    expect(() => playSendChirp()).not.toThrow();
  });

  it('does not throw when Web Audio ramps fail', () => {
    vi.stubGlobal(
      'AudioContext',
      class {
        currentTime = 0;
        destination = {};
        createOscillator() {
          return {
            type: 'square',
            frequency: { value: 0 },
            connect() {},
            start() {},
            stop() {},
          };
        }
        createGain() {
          return {
            gain: {
              value: 0,
              setValueAtTime() {},
              exponentialRampToValueAtTime() {
                throw new Error('InvalidStateError');
              },
            },
            connect() {},
          };
        }
      },
    );
    expect(() => playKeyClick()).not.toThrow();
    expect(() => playSendChirp()).not.toThrow();
  });
});
