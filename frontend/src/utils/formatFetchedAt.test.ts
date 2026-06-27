import { describe, expect, it } from 'vitest';
import {
  formatFetchedAtLocal,
  localizeDataFetchedMarkers,
  parseUtcTimestamp,
} from './formatFetchedAt';

describe('formatFetchedAt', () => {
  it('parses backend UTC space format', () => {
    const date = parseUtcTimestamp('2026-06-27 03:48:35 UTC');
    expect(date?.toISOString()).toBe('2026-06-27T03:48:35.000Z');
  });

  it('localizes Data fetched markers in message text', () => {
    const input = [
      '2-day forecast for Dallas, Texas, United States.',
      'Data fetched: 2026-06-27 03:48:35 UTC',
    ].join('\n');

    const output = localizeDataFetchedMarkers(input);
    expect(output).toContain('2-day forecast for Dallas, Texas, United States.');
    expect(output).not.toContain('03:48:35 UTC');
    expect(output).toMatch(/^Data fetched: .+/m);
  });

  it('localizes Source · Fetched footer markers', () => {
    const input = 'Source: Open-Meteo · Fetched: 2026-06-27 03:48:35 UTC';
    const output = localizeDataFetchedMarkers(input);
    expect(output).toContain('Source: Open-Meteo · Fetched:');
    expect(output).not.toContain('03:48:35 UTC');
  });

  it('returns the original string when parsing fails', () => {
    expect(formatFetchedAtLocal('not-a-date')).toBe('not-a-date');
  });
});
