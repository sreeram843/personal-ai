import { describe, expect, it } from 'vitest';
import { parseReasoningSections } from './parseReasoningSections';

describe('parseReasoningSections', () => {
  it('turns ### Synthesizer markdown into a titled section', () => {
    const sections = parseReasoningSections(
      "### Synthesizer\nThe user wants a simple sentence. Keep it brief.",
    );
    expect(sections).toEqual([
      {
        title: 'Synthesizer',
        body: 'The user wants a simple sentence. Keep it brief.',
      },
    ]);
  });

  it('supports multiple stage headers', () => {
    const sections = parseReasoningSections(
      "### Planner\nPlan a short answer.\n\n### Synthesizer\nDraft one sentence.",
    );
    expect(sections).toHaveLength(2);
    expect(sections[0]?.title).toBe('Planner');
    expect(sections[1]?.title).toBe('Synthesizer');
  });

  it('keeps preamble text without a header', () => {
    const sections = parseReasoningSections('Just some freeform thinking.');
    expect(sections).toEqual([{ title: null, body: 'Just some freeform thinking.' }]);
  });
});
