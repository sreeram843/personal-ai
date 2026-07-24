import { useEffect, useId, useState } from 'react';

interface Props {
  source: string;
}

let mermaidModule: typeof import('mermaid').default | null = null;

function readCssVar(name: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

/** Pull the app's own design tokens into Mermaid's theme so diagrams render
 * as tinted cards/lines matching the rest of the chat UI, instead of Mermaid's
 * generic default palette. */
function buildThemeVariables() {
  const tileBg = readCssVar('--ui-bg-elevated');
  const border = readCssVar('--ui-border-strong') || readCssVar('--ui-border');
  const textPrimary = readCssVar('--text-primary');
  const accent = readCssVar('--ui-accent') || '#e0a446';

  return {
    background: 'transparent',
    primaryColor: tileBg,
    primaryBorderColor: border,
    primaryTextColor: textPrimary,
    lineColor: border,
    textColor: textPrimary,
    mainBkg: tileBg,
    nodeBorder: border,
    clusterBkg: tileBg,
    clusterBorder: border,
    edgeLabelBackground: tileBg,
    fontFamily: 'ui-sans-serif, system-ui, sans-serif',
    fontSize: '13px',
    tertiaryColor: accent,
  };
}

async function getMermaid() {
  if (!mermaidModule) {
    mermaidModule = (await import('mermaid')).default;
  }
  mermaidModule.initialize({
    startOnLoad: false,
    theme: 'base',
    themeVariables: buildThemeVariables(),
    securityLevel: 'strict',
    fontFamily: 'ui-sans-serif, system-ui, sans-serif',
  });
  return mermaidModule;
}

function useThemeMode(): 'light' | 'dark' {
  const [theme, setTheme] = useState<'light' | 'dark'>(() =>
    document.documentElement.classList.contains('dark') ? 'dark' : 'light',
  );

  useEffect(() => {
    const root = document.documentElement;
    const sync = () => setTheme(root.classList.contains('dark') ? 'dark' : 'light');
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
        const mermaid = await getMermaid();
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
      <div className="message-mermaid message-mermaid--error overflow-hidden rounded-2xl border border-[var(--ui-border)]">
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
        className="message-mermaid flex min-h-[4rem] items-center justify-center rounded-2xl border border-[var(--ui-border)] bg-[var(--ui-bg-elevated)] px-3 py-4 text-sm text-[var(--phosphor-dim)]"
        aria-busy="true"
      >
        Rendering diagram…
      </div>
    );
  }

  return (
    <div
      className="message-mermaid overflow-x-auto rounded-2xl border border-[var(--ui-border)] bg-[var(--ui-bg-elevated)] p-4 shadow-[0_4px_16px_rgba(0,0,0,0.08)]"
      dangerouslySetInnerHTML={{ __html: svg }}
      aria-label="Mermaid diagram"
    />
  );
}
