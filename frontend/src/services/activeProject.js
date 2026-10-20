const ACTIVE_PROJECT_PREFIX = 'qa_active_project_id_';

/**
 * Get active project ID for the current authenticated user.
 * @param {number|string} userId
 * @returns {string|null}
 */
export function getStoredActiveProjectId(userId) {
  if (!userId) return null;
  try {
    const val = localStorage.getItem(`${ACTIVE_PROJECT_PREFIX}${userId}`);
    return val && typeof val === 'string' && val.trim() ? val.trim() : null;
  } catch {
    return null;
  }
}

/**
 * Save active project ID for the current authenticated user.
 * @param {number|string} userId
 * @param {string} projectId
 */
export function setStoredActiveProjectId(userId, projectId) {
  if (!userId) return;
  try {
    if (projectId && typeof projectId === 'string' && projectId.trim()) {
      localStorage.setItem(`${ACTIVE_PROJECT_PREFIX}${userId}`, projectId.trim());
    } else {
      localStorage.removeItem(`${ACTIVE_PROJECT_PREFIX}${userId}`);
    }
  } catch {
    // Graceful storage failure fallback
  }
}

/**
 * Clear stored active project ID for the current authenticated user.
 * @param {number|string} userId
 */
export function clearStoredActiveProjectId(userId) {
  if (!userId) return;
  try {
    localStorage.removeItem(`${ACTIVE_PROJECT_PREFIX}${userId}`);
  } catch {
    // Graceful storage failure fallback
  }
}
