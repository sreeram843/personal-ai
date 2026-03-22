import { useEffect, useRef, useState } from 'react';
import type { KeyboardEvent } from 'react';
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

  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      handleSend();
    }
  };

  if (terminalMode) {
    return (
      <div className="w-full bg-transparent px-0 py-0">
        <label className="flex items-center gap-2 text-[var(--phosphor)]">
          <span className="terminal-font text-xl">[USER1: &gt;]</span>
          <textarea
            className="terminal-font h-8 w-full resize-none bg-transparent text-xl leading-8 text-[var(--phosphor)] placeholder:text-[var(--phosphor-dim)] outline-none"
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
          <span className="terminal-cursor text-xl">█</span>
        </label>
      </div>
    );
  }

  return (
    <div className="flex items-end gap-3 rounded-lg border border-[#007f1f] bg-[#001000] p-3">
      <div className="relative flex-1">
        <textarea
          className="h-20 w-full resize-none bg-black text-[var(--phosphor)] placeholder:text-[var(--phosphor-dim)] outline-none"
          placeholder="> ENTER COMMAND"
          value={value}
          onChange={(event) => {
            if (event.target.value.length > value.length) {
              playKeyClick();
            }
            setValue(event.target.value);
          }}
          onKeyDown={handleKeyDown}
          disabled={disabled}
        />
        <span className="terminal-cursor absolute right-3 bottom-2 text-[var(--phosphor)]">{terminalMode ? '█' : '|'}</span>
      </div>
      <div className="flex flex-col gap-2">
        <button
          type="button"
          onClick={() => setIsRecording((state) => !state)}
          disabled={disabled}
          className="grid h-10 w-10 place-content-center rounded-lg border border-[#004010] text-[#00ff41] transition hover:bg-[#002000] disabled:cursor-not-allowed disabled:opacity-50"
          title={isRecording ? 'Stop recording' : 'Voice input'}
        >
          {isRecording ? <MicOff className="h-5 w-5" /> : <Mic className="h-5 w-5" />}
        </button>
        <button
          type="button"
          onClick={handleSend}
          disabled={disabled || !value.trim()}
          className="grid h-10 w-10 place-content-center rounded-lg bg-[#004010] text-[#00ff41] transition hover:bg-[#005020] disabled:cursor-not-allowed disabled:opacity-50"
          title="Send"
        >
          <Send className="h-5 w-5" />
        </button>
      </div>
    </div>
  );
}
