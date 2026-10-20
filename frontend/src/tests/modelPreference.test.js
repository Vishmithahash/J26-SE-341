import './setup.js';
import { describe, it, beforeEach } from 'node:test';
import assert from 'node:assert/strict';
import {
  getModelPreference,
  saveModelPreference,
  clearModelPreference,
} from '../services/modelPreference.js';

describe('Model Preference Isolation and Storage Resilience', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('correctly saves and retrieves model preference for a specific user ID', () => {
    const prefUser1 = {
      connectionType: 'local',
      provider: 'ollama',
      modelId: 'llama3.1:8b',
    };

    saveModelPreference(101, prefUser1);
    const retrieved = getModelPreference(101);

    assert.notEqual(retrieved, null);
    assert.equal(retrieved?.modelId, 'llama3.1:8b');
    assert.equal(retrieved?.provider, 'ollama');
    assert.equal(retrieved?.connectionType, 'local');
  });

  it('guarantees account B does NOT inherit account A preference (user isolation)', () => {
    saveModelPreference(101, {
      connectionType: 'local',
      provider: 'ollama',
      modelId: 'llama3:8b',
    });

    saveModelPreference(102, {
      connectionType: 'hosted',
      provider: 'openai-compatible',
      modelId: 'gpt-4o-mini',
    });

    const user1Pref = getModelPreference(101);
    const user2Pref = getModelPreference(102);
    const unconfiguredUserPref = getModelPreference(103);

    assert.equal(user1Pref?.modelId, 'llama3:8b');
    assert.equal(user2Pref?.modelId, 'gpt-4o-mini');
    assert.equal(unconfiguredUserPref, null);
  });

  it('resets preference cleanly without affecting other accounts', () => {
    saveModelPreference(201, {
      connectionType: 'local',
      provider: 'ollama',
      modelId: 'mistral-small',
    });
    saveModelPreference(202, {
      connectionType: 'hosted',
      provider: 'openai-compatible',
      modelId: 'gpt-4o',
    });

    clearModelPreference(201);

    assert.equal(getModelPreference(201), null);
    assert.equal(getModelPreference(202)?.modelId, 'gpt-4o');
  });

  it('survives corrupted or malformed browser storage gracefully without crashing', () => {
    // Malformed JSON string in storage
    localStorage.setItem('qa_model_pref_999', 'INVALID_JSON{{{');
    assert.equal(getModelPreference(999), null);

    // Invalid non-object structure
    localStorage.setItem('qa_model_pref_998', JSON.stringify('a plain string'));
    assert.equal(getModelPreference(998), null);

    // Invalid connection type
    localStorage.setItem(
      'qa_model_pref_997',
      JSON.stringify({ connectionType: 'invalid-cloud', modelId: 'test' })
    );
    assert.equal(getModelPreference(997), null);
  });
});
