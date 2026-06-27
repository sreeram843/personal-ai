import { Check, Copy } from 'lucide-react';
import { useEffect, useState } from 'react';
import { codeToHtml } from 'shiki';

interface Props {
  language: string;
  code: string;
}

function useIsDarkTheme(): boolean {
  const [isDark, setIsDark] = useState(() =>
    typeof document !== 'undefined' ? document.documentElement.classList.contains('dark') : false,
  );

  useEffect(() => {
    const root = document.documentElement;
    const observer = new MutationObserver(() => {
      setIsDark(root.classList.contains('dark'));
    });
    observer.observe(root, { attributes: true, attributeFilter: ['class'] });
    return () => observer.disconnect();
  }, []);

  return isDark;
}

async function highlightCode(code: string, language: string, isDark: boolean): Promise<string> {
  const lang = language.trim() || 'text';
  const theme = isDark ? 'github-dark' : 'github-light';
  try {
    return await codeToHtml(code, { lang, theme });
  } catch {
    return await codeToHtml(code, { lang: 'text', theme });
  }
}

export function ShikiCodeBlock({ language, code }: Props) {
  const isDark = useIsDarkTheme();
  const [html, setHtml] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const displayLang = language.trim() || 'text';

  useEffect(() => {
    let cancelled = false;
    void highlightCode(code, displayLang, isDark).then((result) => {
      if (!cancelled) {
        setHtml(result);
      }
    });
    return () => {
      cancelled = true;
    };
  }, [code, displayLang, isDark]);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1600);
    } catch {
      setCopied(false);
    }
  };

  return (
    <div className="message-code-block shiki-block overflow-hidden rounded-xl border border-[var(--ui-border)]">
      <div className="flex items-center justify-between gap-2 border-b border-[var(--ui-border)] bg-[var(--ui-bg-elevated)] px-3 py-1.5">
        <span className="classic-mono text-[11px] uppercase tracking-wide text-[var(--phosphor-dim)]">
          {displayLang}
        </span>
        <button
          type="button"
          onClick={() => void handleCopy()}
          className="grid h-7 w-7 place-content-center rounded-md text-[var(--phosphor-dim)] transition hover:bg-[var(--ui-bg)] hover:text-[var(--phosphor)]"
          aria-label={copied ? 'Copied' : 'Copy code'}
          title={copied ? 'Copied' : 'Copy'}
        >
          {copied ? <Check className="h-3.5 w-3.5" aria-hidden /> : <Copy className="h-3.5 w-3.5" aria-hidden />}
        </button>
      </div>
      {html ? (
        <div
          className="shiki-wrapper overflow-x-auto text-[0.8125rem] leading-relaxed [&_pre]:m-0 [&_pre]:bg-transparent [&_pre]:p-3"
          dangerouslySetInnerHTML={{ __html: html }}
        />
      ) : (
        <pre className="classic-mono overflow-x-auto bg-[var(--ui-bg)] p-3 text-[0.8125rem] leading-relaxed text-[var(--phosphor-bright)]">
          <code>{code}</code>
        </pre>
      )}
    </div>
  );
}
