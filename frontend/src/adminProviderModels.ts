/** Curated model ids per Admin provider name — used by Routing dropdowns. */

export const PROVIDER_MODELS: Record<string, readonly string[]> = {
  groq: ['openai/gpt-oss-20b', 'openai/gpt-oss-120b'],
  perplexity: ['sonar', 'sonar-pro', 'sonar-reasoning-pro'],
  gemini: ['gemini-flash-latest', 'gemini-3.6-flash', 'gemini-3.1-flash-lite'],
  openai: ['gpt-4o-mini', 'gpt-4o', 'gpt-4.1-mini', 'gpt-4.1'],
  deepseek: ['deepseek-v4-flash', 'deepseek-v4-pro'],
  kimi: ['kimi-k2.6', 'kimi-k3', 'kimi-k2.7-code', 'kimi-k2.7-code-highspeed'],
  moonshot: ['kimi-k2.6', 'kimi-k3', 'kimi-k2.7-code', 'kimi-k2.7-code-highspeed'],
  qwen: ['qwen-plus', 'qwen-turbo', 'qwen-max', 'qwen-flash'],
  ollama: ['llama3.2', 'llama3.1', 'mistral', 'qwen2.5', 'phi3'],
};

export function modelsForProvider(provider: string): string[] {
  const key = (provider || '').trim().toLowerCase();
  return [...(PROVIDER_MODELS[key] ?? [])];
}

export function defaultModelForProvider(provider: string): string {
  return modelsForProvider(provider)[0] ?? '';
}

/** Options for a model `<select>`, keeping a legacy saved value visible until changed. */
export function modelSelectOptions(provider: string, currentModel: string): string[] {
  const catalog = modelsForProvider(provider);
  const current = (currentModel || '').trim();
  if (current && !catalog.includes(current)) {
    return [current, ...catalog];
  }
  return catalog;
}
