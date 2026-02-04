import { useEffect, useRef, useState } from 'react';
import type { KeyboardEvent } from 'react';
import { Mic, MicOff, Send } from 'lucide-react';

interface Props {
  disabled?: boolean;
  onSend: (message: string) => void;
}

export function ChatInput({ disabled, onSend }: Props) {
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
    <div className="flex items-end gap-3 rounded-3xl border border-gray-200 bg-white p-3 shadow-lg dark:border-zinc-700 dark:bg-zinc-800">
      <textarea
        className="h-20 w-full resize-none bg-transparent text-base leading-relaxed text-gray-900 outline-none dark:text-zinc-100"
        placeholder="Ask anything..."
        value={value}
        onChange={(event) => setValue(event.target.value)}
        onKeyDown={handleKeyDown}
        disabled={disabled}
      />
      <div className="flex flex-col gap-2">
        <button
          type="button"
          onClick={() => setIsRecording((state) => !state)}
          disabled={disabled}
          className="grid h-10 w-10 place-content-center rounded-full border border-gray-200 text-gray-500 transition hover:bg-gray-100 disabled:cursor-not-allowed disabled:opacity-50 dark:border-zinc-700 dark:hover:bg-zinc-700"
          title={isRecording ? 'Stop recording' : 'Voice input'}
        >
          {isRecording ? <MicOff className="h-5 w-5" /> : <Mic className="h-5 w-5" />}
        </button>
        <button
          type="button"
          onClick={handleSend}
          disabled={disabled || !value.trim()}
          className="grid h-10 w-10 place-content-center rounded-full bg-emerald-500 text-white transition hover:bg-emerald-600 disabled:cursor-not-allowed disabled:bg-emerald-300"
          title="Send"
        >
          <Send className="h-5 w-5" />
        </button>
      </div>
    </div>
  );
}
