import { useEffect, useId, useState } from 'react';

interface Props {
  source: string;
}

let mermaidModule: typeof import('mermaid').default | null = null;

async function getMermaid(theme: 'neutral' | 'dark') {
  if (!mermaidModule) {
    mermaidModule = (await import('mermaid')).default;
  }
  mermaidModule.initialize({
    startOnLoad: false,
    theme,
    securityLevel: 'strict',
    fontFamily: 'ui-sans-serif, system-ui, sans-serif',
  });
  return mermaidModule;
}

function useThemeMode(): 'neutral' | 'dark' {
  const [theme, setTheme] = useState<'neutral' | 'dark'>(() =>
    document.documentElement.classList.contains('dark') ? 'dark' : 'neutral',
  );

  useEffect(() => {
    const root = document.documentElement;
    const sync = () => setTheme(root.classList.contains('dark') ? 'dark' : 'neutral');
    const observer = new MutationObserver(sync);
    observer.observe(root, { attributes: true, attributeFilter: ['class'] });
    return () => observer.disconnect();
  }, []);

  return theme;
}

/** Render a Mermaid diagram from assistant markdown. */
export function MermaidDiagram({ source }: Props) {
  const diagram = source.replace(/\n$/, '').trim();
  const reactId = useId().replace(/:/g, '');
  const renderId = `mermaid-${reactId}`;
  const theme = useThemeMode();
  const [svg, setSvg] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    if (!diagram) return;

    let cancelled = false;

    void (async () => {
      try {
        const mermaid = await getMermaid(theme);
        if (cancelled) return;

        const { svg: rendered } = await mermaid.render(renderId, diagram);
        if (!cancelled) {
          setSvg(rendered);
          setError('');
        }
      } catch (err) {
        if (!cancelled) {
          setSvg('');
          setError(err instanceof Error ? err.message : 'Could not render diagram');
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [diagram, renderId, theme]);

  if (error) {
    return (
      <div className="message-mermaid message-mermaid--error overflow-hidden rounded-xl border border-[var(--ui-border)]">
        <div className="border-b border-[var(--ui-border)] bg-[var(--ui-bg-elevated)] px-3 py-1.5 text-[11px] uppercase tracking-wide text-[var(--phosphor-dim)]">
          Diagram (preview unavailable)
        </div>
        <pre className="classic-mono overflow-x-auto bg-[var(--ui-bg)] p-3 text-[0.8125rem] text-[var(--phosphor-dim)]">
          {diagram}
        </pre>
      </div>
    );
  }

  if (!svg) {
    return (
      <div
        className="message-mermaid flex min-h-[4rem] items-center justify-center rounded-xl border border-[var(--ui-border)] bg-[var(--ui-bg-elevated)] px-3 py-4 text-sm text-[var(--phosphor-dim)]"
        aria-busy="true"
      >
        Rendering diagram…
      </div>
    );
  }

  return (
    <div
      className="message-mermaid overflow-x-auto rounded-xl border border-[var(--ui-border)] bg-[var(--ui-bg)] p-3"
      dangerouslySetInnerHTML={{ __html: svg }}
      aria-label="Mermaid diagram"
    />
  );
}
