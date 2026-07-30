export interface ReasoningSection {
  title: string | null;
  body: string;
}

/** Split backend `### Stage\\n...` blobs into titled sections for the UI. */
export function parseReasoningSections(reasoning: string): ReasoningSection[] {
  const text = reasoning.trim();
  if (!text) {
    return [];
  }

  const sections: ReasoningSection[] = [];
  let title: string | null = null;
  let bodyLines: string[] = [];

  const flush = () => {
    const body = bodyLines.join('\n').trim();
    if (!title && !body) {
      return;
    }
    sections.push({ title, body });
    title = null;
    bodyLines = [];
  };

  for (const line of text.split('\n')) {
    const match = /^(#{1,6})\s+(.+)$/.exec(line.trim());
    if (match) {
      flush();
      title = match[2].trim();
      continue;
    }
    bodyLines.push(line);
  }
  flush();
  return sections;
}
