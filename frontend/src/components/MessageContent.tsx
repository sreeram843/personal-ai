import type { Components } from 'react-markdown';
import { localizeDataFetchedMarkers } from '../utils/formatFetchedAt';
import ReactMarkdown from 'react-markdown';
import rehypeSanitize, { defaultSchema } from 'rehype-sanitize';
import remarkGfm from 'remark-gfm';
import { MermaidDiagram } from './MermaidDiagram';
import { ShikiCodeBlock } from './ShikiCodeBlock';

interface Props {
  content: string;
  className?: string;
}

const sanitizeSchema = {
  ...defaultSchema,
  attributes: {
    ...defaultSchema.attributes,
    code: [...(defaultSchema.attributes?.code ?? []), ['className']],
    span: [...(defaultSchema.attributes?.span ?? []), ['className'], ['style']],
    pre: [...(defaultSchema.attributes?.pre ?? []), ['className']],
  },
};

const markdownComponents: Components = {
  a({ href, children }) {
    return (
      <a
        href={href}
        target="_blank"
        rel="noopener noreferrer"
        className="message-link font-medium text-[var(--ui-focus)] underline decoration-[var(--ui-focus)]/40 underline-offset-2 hover:decoration-[var(--ui-focus)]"
      >
        {children}
      </a>
    );
  },
  blockquote({ children }) {
    return (
      <blockquote className="border-l-2 border-[rgba(224,164,70,0.35)] pl-4 text-[14px] leading-[1.6] text-[var(--ui-text-secondary)]">
        {children}
      </blockquote>
    );
  },
  pre({ children }) {
    return <>{children}</>;
  },
  code({ className, children }) {
    const match = /language-([\w-]+)/.exec(className ?? '');
    const raw = String(children).replace(/\n$/, '');

    if (!match) {
      return (
        <code className="classic-mono rounded-md border border-[var(--ui-border)] bg-[var(--ui-bg-elevated)] px-1.5 py-0.5 text-[0.8125rem] text-[var(--phosphor-bright)]">
          {children}
        </code>
      );
    }

    const language = match[1];
    if (language === 'mermaid') {
      return <MermaidDiagram source={raw} />;
    }

    return <ShikiCodeBlock language={language} code={raw} />;
  },
  table({ children }) {
    return (
      <div className="message-table-wrap my-3 overflow-x-auto rounded-xl border border-[var(--ui-border)]">
        <table className="message-table min-w-full text-left text-sm">{children}</table>
      </div>
    );
  },
  thead({ children }) {
    return <thead className="bg-[var(--ui-bg-elevated)] text-[var(--phosphor-bright)]">{children}</thead>;
  },
  th({ children }) {
    return (
      <th className="border-b border-[var(--ui-border)] px-3 py-2 text-xs font-semibold uppercase tracking-wide">
        {children}
      </th>
    );
  },
  td({ children }) {
    return <td className="border-b border-[var(--ui-border)] px-3 py-2 align-top text-[var(--phosphor)]">{children}</td>;
  },
  tr({ children }) {
    return <tr className="even:bg-[var(--ui-bg-elevated)]/40">{children}</tr>;
  },
  hr() {
    return <div className="message-section-gap" aria-hidden />;
  },
  p({ children, node }) {
    const text = node?.children
      ?.map((child) => ('value' in child ? String(child.value) : ''))
      .join('')
      .trim();
    const isMeta = text ? /^Source:|^Fetched:/i.test(text.replace(/^_(.+)_$/, '$1')) : false;
    return <p className={isMeta ? 'message-meta whitespace-pre-wrap' : 'whitespace-pre-wrap'}>{children}</p>;
  },
  h1({ children }) {
    return (
      <h1 className="font-display mt-3 text-[16px] font-semibold tracking-tight text-[var(--phosphor-bright)] first:mt-0">
        {children}
      </h1>
    );
  },
  h2({ children }) {
    return (
      <h2 className="font-display mt-3.5 text-[16px] font-semibold tracking-tight text-[var(--phosphor-bright)] first:mt-0">
        {children}
      </h2>
    );
  },
  h3({ children }) {
    return (
      <h3 className="font-display mt-3 text-[14.5px] font-semibold tracking-tight text-[var(--phosphor-bright)] first:mt-0">
        {children}
      </h3>
    );
  },
  ul({ children }) {
    return <ul className="list-disc space-y-1 pl-5">{children}</ul>;
  },
  ol({ children }) {
    return <ol className="list-decimal space-y-1 pl-5">{children}</ol>;
  },
  li({ children }) {
    return <li className="pl-1">{children}</li>;
  },
};

/** Render assistant/user markdown with GFM tables, Shiki code blocks, and sanitized HTML. */
export function MessageContent({ content, className = '' }: Props) {
  const localizedContent = localizeDataFetchedMarkers(content);

  return (
    <div className={`message-prose space-y-2 text-[var(--phosphor)] ${className}`}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[[rehypeSanitize, sanitizeSchema]]}
        components={markdownComponents}
      >
        {localizedContent}
      </ReactMarkdown>
    </div>
  );
}
