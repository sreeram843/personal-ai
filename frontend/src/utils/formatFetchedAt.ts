const UTC_SPACE_PATTERN = /^(\d{4}-\d{2}-\d{2}) (\d{2}:\d{2}:\d{2}) UTC$/;

/** Parse backend UTC timestamps (space-separated or ISO) into a Date. */
export function parseUtcTimestamp(value: string): Date | null {
  const trimmed = value.trim();
  if (!trimmed) {
    return null;
  }

  const match = trimmed.match(UTC_SPACE_PATTERN);
  if (match) {
    const date = new Date(`${match[1]}T${match[2]}Z`);
    return Number.isNaN(date.getTime()) ? null : date;
  }

  const date = new Date(trimmed);
  return Number.isNaN(date.getTime()) ? null : date;
}

/** Format a UTC timestamp string in the viewer's local timezone and locale. */
export function formatFetchedAtLocal(value?: string): string | undefined {
  if (!value?.trim()) {
    return undefined;
  }

  const date = parseUtcTimestamp(value);
  if (!date) {
    return value;
  }

  return new Intl.DateTimeFormat(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
    second: '2-digit',
    timeZoneName: 'short',
  }).format(date);
}

/** Rewrite provenance markers in assistant markdown to the browser timezone. */
export function localizeDataFetchedMarkers(content: string): string {
  if (!content) {
    return content;
  }

  let result = content.replace(/^Data fetched:\s*(.+)$/gm, (match, timestamp: string) => {
    const local = formatFetchedAtLocal(timestamp.trim());
    return local ? `Data fetched: ${local}` : match;
  });

  result = result.replace(
    /(Source:[^\n]* · Fetched:\s*)(.+)$/gm,
    (match, prefix: string, timestamp: string) => {
      const local = formatFetchedAtLocal(timestamp.trim());
      return local ? `${prefix}${local}` : match;
    },
  );

  return result;
}

export function formatFreshness(asOf?: string, source?: string, confidence?: number): string {
  const parts = [];
  const local = formatFetchedAtLocal(asOf);
  if (local) {
    parts.push(`Data fetched: ${local}`);
  }
  if (source) {
    parts.push(source);
  }
  if (typeof confidence === 'number' && Number.isFinite(confidence) && confidence > 0) {
    parts.push(`${Math.round(confidence * 100)}% confidence`);
  }
  return parts.join(' · ');
}
