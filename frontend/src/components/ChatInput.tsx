import { useEffect, useId, useLayoutEffect, useRef, useState } from 'react';
import type { KeyboardEvent, ChangeEvent } from 'react';
import { Mic, MicOff, Paperclip, Send } from 'lucide-react';
import { playKeyClick, playSendChirp } from '../utils/terminalAudio';

interface Props {
  disabled?: boolean;
  onSend: (message: string) => void;
  onAttach?: () => void;
  hideAttach?: boolean;
  hideVoice?: boolean;
  placeholder?: string;
}

const MIN_TA = 44;
const MAX_TA = 200;

export function ChatInput({ disabled, onSend, onAttach, hideAttach, hideVoice, placeholder = 'Message…' }: Props) {
  const [value, setValue] = useState('');
  const [isRecording, setIsRecording] = useState(false);
  const recognitionRef = useRef<SpeechRecognition | null>(null);
  const textRef = useRef<HTMLTextAreaElement>(null);
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

  useLayoutEffect(() => {
    const el = textRef.current;
    if (!el) {
      return;
    }
    el.style.height = '0px';
    const h = Math.min(MAX_TA, Math.max(MIN_TA, el.scrollHeight));
    el.style.height = `${h}px`;
  }, [value]);

  const handleSend = () => {
    if (!value.trim() || disabled) {
      return;
    }
    playSendChirp();
    onSend(value.trim());
    setValue('');
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="input-composer flex items-center gap-1.5 rounded-3xl border border-[var(--ui-border)] bg-[var(--ui-panel)] px-3 py-2 shadow-lg sm:gap-2">
        <label htmlFor={inputId} className="sr-only">Message input</label>
        <textarea
          ref={textRef}
          id={inputId}
          rows={1}
          className="composer-textarea min-h-[44px] min-w-0 max-h-[200px] flex-1 resize-none overflow-y-auto bg-transparent py-2 text-base leading-normal text-[var(--phosphor)] placeholder:text-[var(--phosphor-dim)] placeholder:opacity-80"
          placeholder={placeholder}
          aria-label="Message input"
          value={value}
          onChange={(event: ChangeEvent<HTMLTextAreaElement>) => {
            if (event.target.value.length > value.length) {
              playKeyClick();
            }
            setValue(event.target.value);
          }}
          onKeyDown={handleKeyDown}
          disabled={disabled}
        />
        {!hideAttach && (
        <button
          type="button"
          onClick={onAttach}
          aria-label="Attach file"
          className="touch-target grid h-10 w-10 shrink-0 place-content-center rounded-lg border border-[var(--ui-border)] text-[var(--phosphor)] transition hover:bg-[var(--ui-bg-elevated)] active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-50 self-center md:h-9 md:w-9"
          title="Attach"
        >
          <Paperclip className="h-4 w-4" />
        </button>
        )}
        {!hideVoice && (
        <button
          type="button"
          onClick={() => setIsRecording((state) => !state)}
          disabled={disabled}
          aria-pressed={isRecording}
          aria-label={isRecording ? 'Stop voice input' : 'Start voice input'}
          className="touch-target grid h-10 w-10 shrink-0 place-content-center rounded-lg border border-[var(--ui-border)] text-[var(--phosphor)] transition hover:bg-[var(--ui-bg-elevated)] active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-50 self-center md:h-9 md:w-9"
          title={isRecording ? 'Stop recording' : 'Voice input'}
        >
          {isRecording ? <MicOff className="h-4 w-4" /> : <Mic className="h-4 w-4" />}
        </button>
        )}
        <button
          type="button"
          onClick={handleSend}
          disabled={disabled || !value.trim()}
          aria-label="Send message"
          className="touch-target grid h-10 w-10 shrink-0 place-content-center self-center rounded-lg bg-[var(--ui-focus)] text-[var(--ui-accent-fg)] shadow-sm transition hover:opacity-90 active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-50 md:h-9 md:w-9"
          title="Send"
        >
          <Send className="h-4 w-4" />
        </button>
    </div>
  );
}
