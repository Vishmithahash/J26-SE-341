import { describe, it, beforeEach } from 'node:test';
import assert from 'node:assert/strict';
import {
  getStoredActiveProjectId,
  setStoredActiveProjectId,
  clearStoredActiveProjectId,
} from '../services/activeProject.js';
import { projectsApi, CONNECTION_STATES } from '../services/projects.js';

// Polyfill minimal browser localStorage for headless Node test environment
if (typeof globalThis.localStorage === 'undefined') {
  const store = new Map();
  globalThis.localStorage = {
    getItem: (k) => (store.has(k) ? store.get(k) : null),
    setItem: (k, v) => store.set(k, String(v)),
    removeItem: (k) => store.delete(k),
    clear: () => store.clear(),
  };
}

describe('Shared Projects Frontend Tests', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  describe('Active Project Account Scoping and Storage Isolation', () => {
    it('saves and retrieves active project ID strictly scoped to user account', () => {
      setStoredActiveProjectId(101, 'proj-alpha-101');
      setStoredActiveProjectId(202, 'proj-beta-202');

      assert.equal(getStoredActiveProjectId(101), 'proj-alpha-101');
      assert.equal(getStoredActiveProjectId(202), 'proj-beta-202');
    });

    it('does not leak active project from User A to User B', () => {
      setStoredActiveProjectId(5, 'proj-user-5');

      assert.equal(getStoredActiveProjectId(5), 'proj-user-5');
      assert.equal(getStoredActiveProjectId(6), null);
    });

    it('clears active project ID when account clears or deselects', () => {
      setStoredActiveProjectId(5, 'proj-user-5');
      assert.equal(getStoredActiveProjectId(5), 'proj-user-5');

      clearStoredActiveProjectId(5);
      assert.equal(getStoredActiveProjectId(5), null);
    });

    it('handles null, undefined, or empty userId gracefully without exceptions', () => {
      assert.equal(getStoredActiveProjectId(null), null);
      assert.equal(getStoredActiveProjectId(undefined), null);
      assert.equal(getStoredActiveProjectId(''), null);

      setStoredActiveProjectId(null, 'proj-123');
      clearStoredActiveProjectId(null);
    });

    it('gracefully handles empty strings and whitespace without storing invalid IDs', () => {
      setStoredActiveProjectId(5, '   ');
      assert.equal(getStoredActiveProjectId(5), null);
    });
  });

  describe('Connection States and Safe Outbound Configuration', () => {
    it('defines distinct honest connection states', () => {
      assert.equal(CONNECTION_STATES.CONNECTED, 'CONNECTED');
      assert.equal(CONNECTION_STATES.PARTIAL, 'PARTIAL');
      assert.equal(CONNECTION_STATES.UNREACHABLE, 'UNREACHABLE');
      assert.equal(CONNECTION_STATES.AUTH_REQUIRED, 'AUTH_REQUIRED');
      assert.equal(CONNECTION_STATES.INVALID_CONFIGURATION, 'INVALID_CONFIGURATION');
      assert.equal(CONNECTION_STATES.DISCONNECTED, 'DISCONNECTED');
      assert.equal(CONNECTION_STATES.NOT_CHECKED, 'NOT_CHECKED');
    });

    it('contains no test-execution or evaluation functions in projectsApi', () => {
      const keys = Object.keys(projectsApi);
      for (const key of keys) {
        assert.doesNotMatch(key, /execute/i, `projectsApi should not have execution methods: ${key}`);
        assert.doesNotMatch(key, /evaluate/i, `projectsApi should not have evaluation methods: ${key}`);
        assert.doesNotMatch(key, /infer/i, `projectsApi should not have model inference methods: ${key}`);
      }
    });
  });
});
