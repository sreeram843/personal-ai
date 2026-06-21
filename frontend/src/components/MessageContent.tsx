import { Fragment, useMemo, type ReactNode } from 'react';
import { MermaidDiagram } from './MermaidDiagram';

interface Props {
  content: string;
  className?: string;
}

type Block =
  | { type: 'code'; language: string; code: string }
  | { type: 'text'; text: string };

/** Render assistant/user markdown: headings, lists, bold, inline + fenced code. */
export function MessageContent({ content, className = '' }: Props) {
  const blocks = useMemo(() => splitMarkdownBlocks(content), [content]);

  return (
    <div className={`message-prose space-y-2 text-[var(--phosphor)] ${className}`}>
      {blocks.map((block, index) =>
        block.type === 'code' ? (
          <CodeBlock key={`code-${index}`} language={block.language} code={block.code} />
        ) : (
          <TextBlock key={`text-${index}`} text={block.text} />
        ),
      )}
    </div>
  );
}

function CodeBlock({ language, code }: { language: string; code: string }) {
  if (language.toLowerCase() === 'mermaid') {
    return <MermaidDiagram source={code} />;
  }

  return (
    <div className="message-code-block overflow-hidden rounded-xl border border-[var(--ui-border)]">
      {language && (
        <div className="flex items-center border-b border-[var(--ui-border)] bg-[var(--ui-bg-elevated)] px-3 py-1.5">
          <span className="classic-mono text-[11px] uppercase tracking-wide text-[var(--phosphor-dim)]">
            {language}
          </span>
        </div>
      )}
      <pre className="classic-mono overflow-x-auto bg-[var(--ui-bg)] p-3 text-[0.8125rem] leading-relaxed text-[var(--phosphor-bright)]">
        <code>{code.replace(/\n$/, '')}</code>
      </pre>
    </div>
  );
}

function TextBlock({ text }: { text: string }) {
  const lines = text.replace(/\r\n/g, '\n').split('\n');
  const nodes: ReactNode[] = [];
  let key = 0;
  let index = 0;

  while (index < lines.length) {
    const line = lines[index];
    const trimmed = line.trim();

    if (!trimmed) {
      index += 1;
      continue;
    }

    if (isHorizontalRule(trimmed)) {
      index += 1;
      nodes.push(<div key={key++} className="message-section-gap" aria-hidden />);
      continue;
    }

    const heading = trimmed.match(/^(#{1,3})\s+(.+)$/);
    if (heading) {
      const level = heading[1].length;
      const textContent = stripHeadingMarkers(heading[2]);
      const className =
        level === 1
          ? 'text-lg font-semibold text-[var(--phosphor-bright)]'
          : level === 2
            ? 'text-base font-semibold text-[var(--phosphor-bright)]'
            : 'text-[15px] font-semibold text-[var(--phosphor-bright)]';
      const headingMargin =
        level === 1 ? 'mt-3 first:mt-0' : level === 2 ? 'mt-4 first:mt-0' : 'mt-3 first:mt-0';
      nodes.push(
        <div key={key++} className={`${className} ${headingMargin}`}>
          {parseInlineMarkdown(textContent)}
        </div>,
      );
      index += 1;
      continue;
    }

    if (/^[-*•]\s+/.test(trimmed)) {
      const items: ReactNode[] = [];
      while (index < lines.length && /^[-*•]\s+/.test(lines[index].trim())) {
        items.push(
          <li key={key++} className="ml-4 list-disc pl-1">
            {parseInlineMarkdown(lines[index].trim().replace(/^[-*•]\s+/, ''))}
          </li>,
        );
        index += 1;
      }
      nodes.push(
        <ul key={key++} className="space-y-1 pl-1">
          {items}
        </ul>,
      );
      continue;
    }

    if (/^\d+\.\s+/.test(trimmed)) {
      const items: ReactNode[] = [];
      while (index < lines.length && /^\d+\.\s+/.test(lines[index].trim())) {
        items.push(
          <li key={key++} className="ml-4 list-decimal pl-1">
            {parseInlineMarkdown(lines[index].trim().replace(/^\d+\.\s+/, ''))}
          </li>,
        );
        index += 1;
      }
      nodes.push(
        <ol key={key++} className="space-y-1 pl-1">
          {items}
        </ol>,
      );
      continue;
    }

    const paragraphLines: string[] = [];
    while (index < lines.length) {
      const current = lines[index].trim();
      if (!current) break;
      if (
        /^(#{1,3})\s+/.test(current) ||
        /^[-*•]\s+/.test(current) ||
        /^\d+\.\s+/.test(current) ||
        isHorizontalRule(current)
      ) {
        break;
      }
      paragraphLines.push(lines[index]);
      index += 1;
    }

    const paragraphText = paragraphLines.join('\n');
    const metaLine = isSourceMetaLine(paragraphText);
    const displayText = metaLine
      ? paragraphText.trim().replace(/^_(.+)_$/, '$1').trim()
      : paragraphText;

    nodes.push(
      <p
        key={key++}
        className={metaLine ? 'message-meta' : 'whitespace-pre-wrap'}
      >
        {parseInlineMarkdown(displayText)}
      </p>,
    );
  }

  return <>{nodes}</>;
}

function splitMarkdownBlocks(content: string): Block[] {
  const blocks: Block[] = [];
  const pattern = /```(\w*)\n?([\s\S]*?)```/g;
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = pattern.exec(content)) !== null) {
    if (match.index > lastIndex) {
      const text = content.slice(lastIndex, match.index).trim();
      if (text) blocks.push({ type: 'text', text });
    }
    blocks.push({ type: 'code', language: match[1] || 'code', code: match[2] });
    lastIndex = match.index + match[0].length;
  }

  const tail = content.slice(lastIndex).trim();
  if (tail) blocks.push({ type: 'text', text: tail });

  if (blocks.length === 0 && content.trim()) {
    blocks.push({ type: 'text', text: content });
  }

  return blocks;
}

function stripHeadingMarkers(text: string): string {
  return text.replace(/^\*\*(.+)\*\*$/, '$1').trim();
}

function isHorizontalRule(line: string): boolean {
  return /^(-{3,}|\*{3,}|_{3,})\s*$/.test(line.trim());
}

function isSourceMetaLine(text: string): boolean {
  const trimmed = text.trim().replace(/^_(.+)_$/, '$1').trim();
  return /^Source:/i.test(trimmed) || /^Fetched:/i.test(trimmed);
}

function parseInlineMarkdown(text: string): ReactNode[] {
  const pattern = /(\*\*(.+?)\*\*|`([^`]+)`|\*(.+?)\*|_(.+?)_)/g;
  const nodes: ReactNode[] = [];
  let lastIndex = 0;
  let key = 0;
  let match: RegExpExecArray | null;

  while ((match = pattern.exec(text)) !== null) {
    if (match.index > lastIndex) {
      nodes.push(<Fragment key={key++}>{text.slice(lastIndex, match.index)}</Fragment>);
    }

    if (match[2] !== undefined) {
      nodes.push(
        <strong key={key++} className="font-semibold text-[var(--phosphor-bright)]">
          {match[2]}
        </strong>,
      );
    } else if (match[3] !== undefined) {
      nodes.push(
        <code
          key={key++}
          className="classic-mono rounded-md border border-[var(--ui-border)] bg-[var(--ui-bg-elevated)] px-1.5 py-0.5 text-[0.8125rem] text-[var(--phosphor-bright)]"
        >
          {match[3]}
        </code>,
      );
    } else if (match[4] !== undefined) {
      nodes.push(
        <em key={key++} className="italic">
          {match[4]}
        </em>,
      );
    } else if (match[5] !== undefined) {
      nodes.push(
        <em key={key++} className="italic text-[var(--phosphor-dim)]">
          {match[5]}
        </em>,
      );
    }

    lastIndex = match.index + match[0].length;
  }

  if (lastIndex < text.length) {
    nodes.push(<Fragment key={key++}>{text.slice(lastIndex)}</Fragment>);
  }

  return nodes.length > 0 ? nodes : [text];
}
