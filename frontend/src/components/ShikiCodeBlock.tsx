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
    <div className="message-code-block shiki-block overflow-hidden rounded-2xl border border-[var(--ui-border)] shadow-[0_4px_16px_rgba(0,0,0,0.08)]">
      <div className="flex items-center justify-between gap-2 border-b border-[var(--ui-border)] bg-[var(--ui-bg-elevated)] px-3.5 py-2">
        <span className="classic-mono text-[11px] uppercase tracking-[0.04em] text-[var(--phosphor-dim)]">
          {displayLang}
        </span>
        <button
          type="button"
          onClick={() => void handleCopy()}
          className="classic-mono cursor-pointer text-[11px] text-[var(--phosphor-dim)] transition hover:text-[var(--phosphor)]"
        >
          {copied ? 'Copied' : 'Copy'}
        </button>
      </div>
      {html ? (
        <div
          className="shiki-wrapper overflow-x-auto text-[12.5px] leading-[1.6] [&_pre]:m-0 [&_pre]:bg-transparent [&_pre]:px-4 [&_pre]:py-3.5"
          dangerouslySetInnerHTML={{ __html: html }}
        />
      ) : (
        <pre className="classic-mono overflow-x-auto bg-[var(--ui-bg)] px-4 py-3.5 text-[12.5px] leading-[1.6] text-[var(--phosphor-bright)]">
          <code>{code}</code>
        </pre>
      )}
    </div>
  );
}
