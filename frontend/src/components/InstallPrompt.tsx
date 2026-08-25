import { useEffect, useState } from 'react';
import { X } from 'lucide-react';
import { isCapacitorNative } from '../platform/capacitor';

const DISMISS_KEY = 'curieai-install-dismissed';

interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed'; platform: string }>;
}

function isDismissed(): boolean {
  try {
    return localStorage.getItem(DISMISS_KEY) === '1';
  } catch {
    return false;
  }
}

function persistDismiss(): void {
  try {
    localStorage.setItem(DISMISS_KEY, '1');
  } catch {
    // Ignore quota / private-mode failures.
  }
}

function isStandaloneDisplay(): boolean {
  if (window.matchMedia('(display-mode: standalone)').matches) {
    return true;
  }
  const nav = window.navigator as Navigator & { standalone?: boolean };
  return nav.standalone === true;
}

function looksLikeIos(userAgent: string): boolean {
  return /iPhone|iPad|iPod/i.test(userAgent);
}

function isBeforeInstallPromptEvent(event: Event): event is BeforeInstallPromptEvent {
  return 'prompt' in event && typeof (event as BeforeInstallPromptEvent).prompt === 'function';
}

export function InstallPrompt() {
  const [deferred, setDeferred] = useState<BeforeInstallPromptEvent | null>(null);
  const [iosHint, setIosHint] = useState(false);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    if (isCapacitorNative() || isDismissed() || isStandaloneDisplay()) {
      return undefined;
    }

    if (looksLikeIos(navigator.userAgent)) {
      setIosHint(true);
      setVisible(true);
    }

    const onBeforeInstallPrompt = (event: Event) => {
      event.preventDefault();
      if (!isBeforeInstallPromptEvent(event)) {
        return;
      }
      setDeferred(event);
      setIosHint(false);
      setVisible(true);
    };

    window.addEventListener('beforeinstallprompt', onBeforeInstallPrompt);
    return () => window.removeEventListener('beforeinstallprompt', onBeforeInstallPrompt);
  }, []);

  if (!visible) {
    return null;
  }

  const dismiss = () => {
    persistDismiss();
    setVisible(false);
    setDeferred(null);
  };

  const install = async () => {
    if (!deferred) {
      return;
    }
    await deferred.prompt();
    await deferred.userChoice;
    persistDismiss();
    setVisible(false);
    setDeferred(null);
  };

  return (
    <div
      role="region"
      aria-label="Install CurieAI"
      className="pointer-events-none fixed inset-x-0 top-0 z-40 flex justify-center px-3 pt-[max(0.5rem,var(--safe-area-top))]"
    >
      <div className="pointer-events-auto flex max-w-lg items-center gap-3 rounded-2xl border border-[var(--ui-border-strong)] bg-[var(--ui-panel-strong)] px-3 py-2 text-[var(--phosphor)] shadow-lg">
        <p className="min-w-0 flex-1 text-[13px] leading-snug">
          {iosHint ? 'Add to Home Screen' : 'Install CurieAI'}
        </p>
        {deferred ? (
          <button
            type="button"
            onClick={() => {
              void install();
            }}
            className="shrink-0 rounded-full bg-[var(--ui-accent)] px-3 py-1.5 text-[12px] font-medium text-[var(--ui-accent-fg)] transition hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ui-focus)]"
          >
            Install
          </button>
        ) : null}
        <button
          type="button"
          onClick={dismiss}
          className="touch-target grid h-8 w-8 shrink-0 place-content-center rounded-lg text-[var(--phosphor-dim)] transition hover:bg-[var(--ui-bg-elevated)] hover:text-[var(--phosphor)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ui-focus)]"
          aria-label="Dismiss install prompt"
        >
          <X className="h-4 w-4" aria-hidden />
        </button>
      </div>
    </div>
  );
}
