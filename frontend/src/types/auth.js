/**
 * @typedef {'ADMIN' | 'USER'} UserRole
 */

/**
 * @typedef {Object} User
 * @property {number} id
 * @property {string} name
 * @property {string} email
 * @property {UserRole} role
 * @property {boolean} is_active
 * @property {string} created_at_utc
 */

/**
 * @typedef {Object} TokenResponse
 * @property {string} access_token
 * @property {string} token_type
 * @property {number} expires_in
 * @property {User} user
 */

/**
 * @typedef {Object} UserListResponse
 * @property {User[]} items
 * @property {number} total
 * @property {number} limit
 * @property {number} offset
 */

/**
 * @typedef {Object} ModelPreference
 * @property {'local' | 'hosted'} connectionType
 * @property {'ollama' | 'openai-compatible' | 'custom'} provider
 * @property {string} modelId
 * @property {string} [updatedAt]
 */

/**
 * @typedef {'light' | 'dark' | 'system'} ThemeMode
 */

/**
 * @typedef {'comfortable' | 'compact'} DisplayDensity
 */

export {};
