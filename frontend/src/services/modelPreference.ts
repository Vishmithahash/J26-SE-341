import type { ModelPreference } from '../types/auth';

const STORAGE_PREFIX = 'qa_model_pref_';

export function getModelPreference(userId: number): ModelPreference | null {
  if (!userId) return null;
  try {
    const raw = localStorage.getItem(`${STORAGE_PREFIX}${userId}`);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed !== 'object') return null;
    if (parsed.connectionType !== 'local' && parsed.connectionType !== 'hosted') return null;
    if (typeof parsed.modelId !== 'string') return null;
    return {
      connectionType: parsed.connectionType,
      provider: parsed.provider || (parsed.connectionType === 'local' ? 'ollama' : 'openai-compatible'),
      modelId: parsed.modelId,
      updatedAt: parsed.updatedAt,
    };
  } catch {
    return null;
  }
}

export function saveModelPreference(userId: number, pref: ModelPreference): void {
  if (!userId) return;
  try {
    localStorage.setItem(
      `${STORAGE_PREFIX}${userId}`,
      JSON.stringify({
        ...pref,
        updatedAt: new Date().toISOString(),
      })
    );
  } catch {
    // Gracefully handle storage quota or privacy mode restrictions
  }
}

export function clearModelPreference(userId: number): void {
  if (!userId) return;
  try {
    localStorage.removeItem(`${STORAGE_PREFIX}${userId}`);
  } catch {
    // Gracefully handle storage access failure
  }
}
