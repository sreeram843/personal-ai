import { useEffect, useRef, useState } from 'react';
import type { KeyboardEvent, ChangeEvent } from 'react';
import { Mic, MicOff, Send } from 'lucide-react';
import { playKeyClick, playSendChirp } from '../utils/terminalAudio';

interface Props {
  disabled?: boolean;
  onSend: (message: string) => void;
  terminalMode?: boolean;
}

export function ChatInput({ disabled, onSend, terminalMode = false }: Props) {
  const [value, setValue] = useState('');
  const [isRecording, setIsRecording] = useState(false);
  const recognitionRef = useRef<SpeechRecognition | null>(null);

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
        <label className="flex items-center gap-2 text-[var(--phosphor)]">
          <span className="terminal-font hidden text-xl sm:inline">[USER1: &gt;]</span>
          <span className="terminal-font text-lg sm:hidden">&gt;</span>
          <textarea
            className="terminal-font h-8 min-w-0 w-full resize-none bg-transparent text-lg leading-8 text-[var(--phosphor)] placeholder:text-[var(--phosphor-dim)] outline-none sm:text-xl"
            placeholder="type command and press Enter"
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
    <div className="flex items-center gap-2 rounded-lg border border-[#007f1f] bg-[#001000] px-3 py-2 sm:gap-3">
      <input
        type="text"
        className="min-w-0 flex-1 bg-transparent text-sm text-[var(--phosphor)] placeholder:text-[var(--phosphor-dim)] outline-none sm:text-base"
        placeholder="> ENTER COMMAND"
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
      <span className="terminal-cursor text-[var(--phosphor)]">|</span>
      <button
        type="button"
        onClick={() => setIsRecording((state) => !state)}
        disabled={disabled}
        className="grid h-8 w-8 shrink-0 place-content-center rounded border border-[#004010] text-[#00ff41] transition hover:bg-[#002000] disabled:cursor-not-allowed disabled:opacity-50"
        title={isRecording ? 'Stop recording' : 'Voice input'}
      >
        {isRecording ? <MicOff className="h-4 w-4" /> : <Mic className="h-4 w-4" />}
      </button>
      <button
        type="button"
        onClick={handleSend}
        disabled={disabled || !value.trim()}
        className="grid h-8 w-8 shrink-0 place-content-center rounded bg-[#004010] text-[#00ff41] transition hover:bg-[#005020] disabled:cursor-not-allowed disabled:opacity-50"
        title="Send"
      >
        <Send className="h-4 w-4" />
      </button>
    </div>
  );
}
