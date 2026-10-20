class MockStorage {
  constructor() {
    this._store = new Map();
  }

  get length() {
    return this._store.size;
  }

  clear() {
    this._store.clear();
  }

  getItem(key) {
    return this._store.has(key) ? this._store.get(key) : null;
  }

  key(index) {
    const keys = Array.from(this._store.keys());
    return keys[index] ?? null;
  }

  removeItem(key) {
    this._store.delete(key);
  }

  setItem(key, value) {
    this._store.set(key, String(value));
  }
}

if (typeof globalThis.localStorage === 'undefined') {
  globalThis.localStorage = new MockStorage();
}

if (typeof globalThis.sessionStorage === 'undefined') {
  globalThis.sessionStorage = new MockStorage();
}
