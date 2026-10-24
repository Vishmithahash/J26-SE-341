import { request } from './api.js';

const STORAGE_PREFIX = 'qa_model_pref_';

export function getModelPreference(userId) {
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
      provider: parsed.provider || (parsed.connectionType === 'local' ? 'ollama' : 'gemini'),
      modelId: parsed.modelId,
      updatedAt: parsed.updatedAt,
    };
  } catch {
    return null;
  }
}

export function saveModelPreference(userId, pref) {
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

export function clearModelPreference(userId) {
  if (!userId) return;
  try {
    localStorage.removeItem(`${STORAGE_PREFIX}${userId}`);
  } catch {
    // Gracefully handle storage access failure
  }
}

/**
 * Fetch server-configured LLM providers and their runtime availability.
 * Authenticated endpoint: GET /api/v1/llm/providers
 */
export async function fetchProviders(signal) {
  return request('/api/v1/llm/providers', {
    method: 'GET',
    signal,
  });
}

/**
 * Fetch authenticated user's authoritative model selection from backend.
 * Authenticated endpoint: GET /api/v1/llm/selection
 */
export async function fetchModelSelection(signal) {
  return request('/api/v1/llm/selection', {
    method: 'GET',
    signal,
  });
}

/**
 * Persist authenticated user's model selection on the backend.
 * Authenticated endpoint: PUT /api/v1/llm/selection
 */
export async function saveModelSelection(selection, signal) {
  return request('/api/v1/llm/selection', {
    method: 'PUT',
    body: JSON.stringify(selection),
    signal,
  });
}

/**
 * Run a bounded connection and inference test against the specified or active provider.
 * Authenticated endpoint: POST /api/v1/llm/test-connection
 */
export async function testLLMConnection(payload = {}, signal) {
  return request('/api/v1/llm/test-connection', {
    method: 'POST',
    body: JSON.stringify(payload),
    signal,
  });
}
