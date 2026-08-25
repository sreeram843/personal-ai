import { clsx } from 'clsx';
import {
  forwardRef,
  useEffect,
  useId,
  useImperativeHandle,
  useLayoutEffect,
  useRef,
  useState,
} from 'react';
import type { ClipboardEvent, KeyboardEvent, ChangeEvent } from 'react';
import { Bot, ChevronDown, MessageSquare, Mic, MicOff, Paperclip, Send, Sparkles, Square } from 'lucide-react';
import type { AssistantSummary, ConversationMode } from '../types';
import { extractPastedFiles } from '../utils/attachmentFiles';
import { estimateTokens, formatCharCount } from '../utils/estimateTokens';
import { playKeyClick, playSendChirp } from '../utils/terminalAudio';

export interface ChatInputHandle {
  focus: () => void;
  setValue: (text: string) => void;
}

interface Props {
  disabled?: boolean;
  isStreaming?: boolean;
  onSend: (message: string) => void;
  onStop?: () => void;
  onAttach?: () => void;
  onFilesPasted?: (files: File[]) => void;
  hideAttach?: boolean;
  hideVoice?: boolean;
  placeholder?: string;
  mode?: ConversationMode;
  onModeChange?: (mode: ConversationMode) => void;
  assistants?: AssistantSummary[];
  selectedAssistantId?: string;
  onSelectAssistant?: (assistantId: string) => void;
  assistantsLoading?: boolean;
}

const MODE_ITEMS: Array<{ id: ConversationMode; label: string; description: string; icon: typeof MessageSquare }> = [
  { id: 'chat', label: 'Chat', description: 'Fast direct replies', icon: MessageSquare },
  { id: 'smart', label: 'Smart', description: 'RAG, tools, and workflows when needed', icon: Sparkles },
];

function ModeToggle({
  mode,
  onModeChange,
}: {
  mode: ConversationMode;
  onModeChange: (mode: ConversationMode) => void;
}) {
  return (
    <div className="composer-mode-toggle inline-flex shrink-0 items-center gap-0.5" role="radiogroup" aria-label="Conversation mode">
      {MODE_ITEMS.map((item) => {
        const Icon = item.icon;
        const isActive = mode === item.id;
        return (
          <button
            key={item.id}
            type="button"
            role="radio"
            aria-checked={isActive}
            aria-label={`${item.label}: ${item.description}`}
            data-active={isActive ? 'true' : 'false'}
            onClick={() => onModeChange(item.id)}
            className="composer-chip touch-target"
            title={`${item.label} — ${item.description}`}
          >
            <Icon className="h-3 w-3 shrink-0" aria-hidden />
            {item.label}
          </button>
        );
      })}
    </div>
  );
}

function ComposerAssistantPicker({
  assistants,
  selectedId,
  onSelect,
  loading,
}: {
  assistants: AssistantSummary[];
  selectedId?: string;
  onSelect: (assistantId: string) => void;
  loading?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement | null>(null);
  const selected = assistants.find((item) => item.id === selectedId) ?? assistants[0];

  useEffect(() => {
    if (!open) {
      return undefined;
    }
    const onPointerDown = (event: MouseEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', onPointerDown);
    return () => document.removeEventListener('mousedown', onPointerDown);
  }, [open]);

  return (
    <div ref={rootRef} className="relative shrink-0">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        className="composer-chip"
        aria-haspopup="listbox"
        aria-expanded={open}
        title="Assistant"
      >
        <Bot className="h-3 w-3 shrink-0" aria-hidden />
        <span className="max-w-[110px] truncate">{loading ? 'Loading…' : selected?.name ?? 'CurieAI'}</span>
        <ChevronDown className={clsx('h-3 w-3 shrink-0 opacity-70 transition', open ? 'rotate-180' : '')} aria-hidden />
      </button>
      {open ? (
        <div className="composer-dropdown" role="listbox">
          {assistants.map((assistant) => (
            <button
              key={assistant.id}
              type="button"
              role="option"
              aria-selected={assistant.id === selectedId}
              disabled={!assistant.enabled}
              data-active={assistant.id === selectedId ? 'true' : 'false'}
              onClick={() => {
                onSelect(assistant.id);
                setOpen(false);
              }}
              className={clsx('panel-rail__dropdown-item', !assistant.enabled ? 'opacity-50' : '')}
            >
              <div className="text-sm font-medium">{assistant.name}</div>
              {assistant.description ? (
                <div className="mt-0.5 text-xs text-[var(--phosphor-dim)]">{assistant.description}</div>
              ) : null}
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}

const MIN_TA = 24;
const HINT_CHAR_THRESHOLD = 500;

export const ChatInput = forwardRef<ChatInputHandle, Props>(function ChatInput(
  {
    disabled,
    isStreaming = false,
    onSend,
    onStop,
    onAttach,
    onFilesPasted,
    hideAttach = false,
    hideVoice = false,
    placeholder = 'Message...',
    mode,
    onModeChange,
    assistants,
    selectedAssistantId,
    onSelectAssistant,
    assistantsLoading = false,
  },
  ref,
) {
  const [value, setValue] = useState('');
  const [isRecording, setIsRecording] = useState(false);
  const [needsScroll, setNeedsScroll] = useState(false);
  const recognitionRef = useRef<SpeechRecognition | null>(null);
  const textRef = useRef<HTMLTextAreaElement>(null);
  const inputId = useId();

  useImperativeHandle(ref, () => ({
    focus: () => {
      textRef.current?.focus();
    },
    setValue: (text: string) => {
      setValue(text);
      requestAnimationFrame(() => {
        textRef.current?.focus();
      });
    },
  }));

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
    // No JS-side height cap here — the box grows with its content instead of
    // scrolling internally. The CSS max-h-[45vh] on the textarea is only a
    // last-resort safety net for pathological pastes; it's never reached by
    // ordinary messages.
    el.style.height = '0px';
    const h = Math.max(MIN_TA, el.scrollHeight);
    el.style.height = `${h}px`;
    // Only turn overflow on once content genuinely exceeds the capped height —
    // el.clientHeight now reflects the CSS max-height clamp, so this stays
    // false for every normal (uncapped) message and the box never shows a
    // scrollbar track just for being empty or short.
    setNeedsScroll(el.scrollHeight > el.clientHeight);
  }, [value]);

  const handleSend = () => {
    if (!value.trim() || disabled) {
      return;
    }
    const message = value.trim();
    onSend(message);
    setValue('');
    playSendChirp();
    requestAnimationFrame(() => {
      textRef.current?.focus();
    });
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      handleSend();
    }
  };

  const handlePaste = (event: ClipboardEvent<HTMLTextAreaElement>) => {
    const files = extractPastedFiles(event);
    if (files.length > 0 && onFilesPasted) {
      event.preventDefault();
      onFilesPasted(files);
    }
  };

  const showLengthHint = value.length >= HINT_CHAR_THRESHOLD;
  const estimatedTokenCount = estimateTokens(value);
  const hasContent = Boolean(value.trim());
  const assistantOptions =
    assistants && assistants.length
      ? assistants
      : [
          {
            id: 'default',
            name: 'CurieAI',
            triggers: [],
            allowed_tools: [],
            enabled: true,
            bundled: true,
            pick_only: false,
            is_default: true,
          },
        ];

  return (
    <div className="flex flex-col gap-1">
      <div
        className={clsx(
          'input-composer flex flex-col rounded-[26px] border border-[var(--ui-border)] bg-[var(--ui-input)] px-2 pb-1.5 pt-2',
          hasContent && 'input-composer--has-content',
        )}
      >
        <div className="flex items-end gap-2 px-2.5">
          <label htmlFor={inputId} className="sr-only">
            Message input
          </label>
          <textarea
            ref={textRef}
            id={inputId}
            rows={1}
            className={clsx(
              'composer-textarea min-h-[24px] min-w-0 max-h-[45vh] flex-1 resize-none bg-transparent py-0.5 text-[14px] leading-[1.45] text-[var(--phosphor)] placeholder:text-[var(--phosphor-dim)] placeholder:opacity-80',
              needsScroll ? 'overflow-y-auto' : 'overflow-y-hidden',
            )}
            placeholder={placeholder}
            aria-label="Message input"
            value={value}
            onChange={(event: ChangeEvent<HTMLTextAreaElement>) => {
              const next = event.target.value;
              setValue(next);
              if (next.length > value.length) {
                playKeyClick();
              }
            }}
            onKeyDown={handleKeyDown}
            onPaste={handlePaste}
            disabled={disabled}
          />
        </div>
        <div className="mt-1 flex items-center justify-between gap-2">
          <div className="flex min-w-0 flex-1 items-center gap-1.5 overflow-visible">
            {!hideAttach && (
              <button
                type="button"
                onClick={onAttach}
                aria-label="Attach file"
                className="touch-target grid h-7 w-7 shrink-0 place-content-center rounded-full text-[var(--phosphor-dim)] transition hover:bg-[var(--ui-bg-elevated)] hover:text-[var(--phosphor)] active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-50"
                title="Attach"
              >
                <Paperclip className="h-[15px] w-[15px]" />
              </button>
            )}
            {mode && onModeChange && <ModeToggle mode={mode} onModeChange={onModeChange} />}
            {onSelectAssistant && (
              <ComposerAssistantPicker
                assistants={assistantOptions}
                selectedId={selectedAssistantId}
                onSelect={onSelectAssistant}
                loading={assistantsLoading}
              />
            )}
          </div>
          <div className="flex shrink-0 items-center gap-1">
            {!hideVoice && (
              <button
                type="button"
                onClick={() => setIsRecording((state) => !state)}
                disabled={disabled}
                aria-pressed={isRecording}
                aria-label={isRecording ? 'Stop voice input' : 'Start voice input'}
                className="touch-target grid h-7 w-7 shrink-0 place-content-center rounded-full text-[var(--phosphor-dim)] transition hover:bg-[var(--ui-bg-elevated)] hover:text-[var(--phosphor)] active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-50"
                title={isRecording ? 'Stop recording' : 'Voice input'}
              >
                {isRecording ? <MicOff className="h-[14px] w-[14px]" /> : <Mic className="h-[14px] w-[14px]" />}
              </button>
            )}
            <button
              type="button"
              onClick={isStreaming ? onStop : handleSend}
              disabled={disabled || (!isStreaming && !hasContent)}
              aria-label={isStreaming ? 'Stop generating' : 'Send message'}
              className={clsx(
                'composer-send-btn touch-target grid h-[32px] w-[32px] shrink-0 place-content-center rounded-full transition active:scale-[0.98] disabled:cursor-not-allowed',
                isStreaming
                  ? 'border border-[var(--ui-border)] bg-[var(--ui-bg-elevated)] text-[var(--phosphor)] hover:bg-[var(--ui-panel)]'
                  : 'composer-send-btn--ready',
              )}
              title={isStreaming ? 'Stop' : 'Send'}
            >
              {isStreaming ? <Square className="h-3.5 w-3.5 fill-current" /> : <Send className="h-[14px] w-[14px]" strokeWidth={2.2} />}
            </button>
          </div>
        </div>
      </div>
      {showLengthHint && (
        <div className="px-3 text-right text-[11px] tabular-nums text-[var(--phosphor-dim)]">
          {formatCharCount(value.length)} chars · ~{formatCharCount(estimatedTokenCount)} tokens
        </div>
      )}
    </div>
  );
});
