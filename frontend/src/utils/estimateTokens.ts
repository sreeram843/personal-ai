/** Rough token estimate for composer hints (≈4 chars per token for English). */
export function estimateTokens(text: string): number {
  const trimmed = text.trim();
  if (!trimmed) {
    return 0;
  }
  return Math.max(1, Math.ceil(trimmed.length / 4));
}

export function formatCharCount(count: number): string {
  return count.toLocaleString();
}
