import { describe, expect, it } from 'vitest';
import {
  defaultModelForProvider,
  modelSelectOptions,
  modelsForProvider,
} from './adminProviderModels';

describe('adminProviderModels', () => {
  it('lists curated models for known providers', () => {
    expect(modelsForProvider('groq')).toContain('openai/gpt-oss-20b');
    expect(modelsForProvider('DeepSeek')).toEqual(['deepseek-v4-flash', 'deepseek-v4-pro']);
    expect(defaultModelForProvider('kimi')).toBe('kimi-k2.6');
  });

  it('returns empty catalog for unknown providers', () => {
    expect(modelsForProvider('custom-vendor')).toEqual([]);
    expect(defaultModelForProvider('custom-vendor')).toBe('');
  });

  it('keeps a legacy saved model visible until changed', () => {
    expect(modelSelectOptions('groq', 'llama-3.1-8b-instant')).toEqual([
      'llama-3.1-8b-instant',
      'openai/gpt-oss-20b',
      'openai/gpt-oss-120b',
    ]);
    expect(modelSelectOptions('groq', 'openai/gpt-oss-20b')).toEqual([
      'openai/gpt-oss-20b',
      'openai/gpt-oss-120b',
    ]);
  });
});
