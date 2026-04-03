import { useEffect, useId, useRef, useState } from 'react';
import type { KeyboardEvent, ChangeEvent } from 'react';
import { Mic, MicOff, Paperclip, Send } from 'lucide-react';
import { playKeyClick, playSendChirp } from '../utils/terminalAudio';

interface Props {
  disabled?: boolean;
  onSend: (message: string) => void;
  terminalMode?: boolean;
  suggestions?: string[];
  onAttach?: () => void;
}

export function ChatInput({ disabled, onSend, terminalMode = false, suggestions = [], onAttach }: Props) {
  const [value, setValue] = useState('');
  const [isRecording, setIsRecording] = useState(false);
  const recognitionRef = useRef<SpeechRecognition | null>(null);
  const inputId = useId();

  useEffect(() => {
    if (!isRecording) {
      recognitionRef.current?.stop();
      recognitionRef.current = null;
      return;
    }

    const SpeechRecognition =
      (window as unknown as { webkitSpeechRecognition?: typeof window.SpeechRecognition })
        .webkitSpeechRecognition || window.SpeechRecognition;

    if (!SpeechRecognition) {
      console.warn('Speech recognition not supported in this browser');
      setIsRecording(false);
      return;
    }

    const recognition = new SpeechRecognition();
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.lang = 'en-US';

    recognition.onresult = (event) => {
      let transcript = '';
      for (let i = event.resultIndex; i < event.results.length; i += 1) {
        transcript += event.results[i][0].transcript;
      }
      setValue((prev) => `${prev.trim()} ${transcript}`.trim());
    };

    recognition.onend = () => {
      setIsRecording(false);
    };

    recognition.start();
    recognitionRef.current = recognition;

    return () => {
      recognition.stop();
    };
  }, [isRecording]);

  const handleSend = () => {
    if (!value.trim() || disabled) {
      return;
    }
    playSendChirp();
    onSend(value.trim());
    setValue('');
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      handleSend();
    }
  };

  if (terminalMode) {
    return (
      <div className="w-full bg-transparent px-0 py-0">
        <label htmlFor={inputId} className="sr-only">Terminal command input</label>
        <label className="flex items-center gap-2 text-[var(--phosphor)]">
          <span className="terminal-font hidden text-xl sm:inline">[USER1: &gt;]</span>
          <span className="terminal-font text-lg sm:hidden">&gt;</span>
          <textarea
            id={inputId}
            className="terminal-font h-8 min-w-0 w-full resize-none bg-transparent text-lg leading-8 text-[var(--phosphor)] placeholder:text-[var(--phosphor-dim)] outline-none sm:text-xl"
            placeholder="type command and press Enter"
            aria-label="Type command and press Enter"
            value={value}
            onChange={(event) => {
              if (event.target.value.length > value.length) {
                playKeyClick();
              }
              setValue(event.target.value.replace(/\n/g, ''));
            }}
            onKeyDown={handleKeyDown}
            disabled={disabled}
            rows={1}
          />
          <span className="terminal-cursor text-lg sm:text-xl">█</span>
        </label>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {suggestions.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {suggestions.map((item) => (
            <button
              key={item}
              type="button"
              onClick={() => setValue(item)}
              className="rounded-full border border-[var(--ui-border)] bg-[var(--ui-bg-elevated)] px-3 py-1 text-xs text-[var(--phosphor-dim)] transition hover:text-[var(--phosphor)]"
            >
              {item}
            </button>
          ))}
        </div>
      )}

      <div className="flex items-center gap-2 rounded-xl border border-[var(--ui-border-strong)] bg-[var(--ui-panel)] px-3 py-2 sm:gap-3">
        <label htmlFor={inputId} className="sr-only">Message input</label>
        <input
          id={inputId}
          type="text"
          className="min-w-0 flex-1 bg-transparent text-sm text-[var(--phosphor)] placeholder:text-[var(--phosphor-dim)] outline-none sm:text-base"
          placeholder="Ask a follow-up..."
          aria-label="Message input"
          value={value}
          onChange={(event: ChangeEvent<HTMLInputElement>) => {
            if (event.target.value.length > value.length) {
              playKeyClick();
            }
            setValue(event.target.value);
          }}
          onKeyDown={handleKeyDown}
          disabled={disabled}
        />
        <button
          type="button"
          onClick={onAttach}
          aria-label="Attach file"
          className="grid h-9 w-9 shrink-0 place-content-center rounded border border-[var(--ui-border)] text-[var(--phosphor)] transition hover:bg-[var(--ui-bg-elevated)] disabled:cursor-not-allowed disabled:opacity-50"
          title="Attach"
        >
          <Paperclip className="h-4 w-4" />
        </button>
        <button
          type="button"
          onClick={() => setIsRecording((state) => !state)}
          disabled={disabled}
          aria-pressed={isRecording}
          aria-label={isRecording ? 'Stop voice input' : 'Start voice input'}
          className="grid h-9 w-9 shrink-0 place-content-center rounded border border-[var(--ui-border)] text-[var(--phosphor)] transition hover:bg-[var(--ui-bg-elevated)] disabled:cursor-not-allowed disabled:opacity-50"
          title={isRecording ? 'Stop recording' : 'Voice input'}
        >
          {isRecording ? <MicOff className="h-4 w-4" /> : <Mic className="h-4 w-4" />}
        </button>
        <button
          type="button"
          onClick={handleSend}
          disabled={disabled || !value.trim()}
          aria-label="Send message"
          className="grid h-9 w-9 shrink-0 place-content-center rounded bg-[var(--ui-focus)] text-white transition hover:brightness-95 disabled:cursor-not-allowed disabled:opacity-50"
          title="Send"
        >
          <Send className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}
