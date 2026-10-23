const TOKEN_KEY = 'qa_auth_token';

class ApiError extends Error {
  constructor(status, message, data) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.data = data;
  }
}

function getStoredToken() {
  return sessionStorage.getItem(TOKEN_KEY);
}

export function setStoredToken(token) {
  if (token) {
    sessionStorage.setItem(TOKEN_KEY, token);
  } else {
    sessionStorage.removeItem(TOKEN_KEY);
  }
}

function parseFastAPIError(data, fallbackMessage) {
  if (!data) return fallbackMessage;
  if (typeof data === 'string') return data;
  if (typeof data.detail === 'string') return data.detail;
  if (Array.isArray(data.detail)) {
    // Array of pydantic errors: [{ loc: [...], msg: "..." }]
    const messages = data.detail.map((err) => {
      const field = Array.isArray(err.loc) ? err.loc[err.loc.length - 1] : '';
      const cleanField = field && field !== 'body' ? `${field}: ` : '';
      return `${cleanField}${err.msg || 'Invalid field'}`;
    });
    return messages.join('. ');
  }
  return fallbackMessage;
}

let onUnauthorizedCallback = null;

export function setOnUnauthorizedCallback(cb) {
  onUnauthorizedCallback = cb;
}

async function request(path, options = {}) {
  const token = getStoredToken();
  const headers = {
    'Content-Type': 'application/json',
    ...options.headers,
  };

  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  let response;
  try {
    response = await fetch(path, {
      ...options,
      headers,
    });
  } catch {
    throw new ApiError(0, 'Unable to connect to the server. Please check your network connection.');
  }

  if (response.status === 401) {
    setStoredToken(null);
    if (onUnauthorizedCallback) {
      onUnauthorizedCallback();
    }
  }

  if (!response.ok) {
    let errorData = null;
    try {
      errorData = await response.json();
    } catch {
      // Body not JSON
    }
    const message = parseFastAPIError(
      errorData,
      response.status === 401
        ? 'Invalid email or password.'
        : response.status === 403
        ? 'Access forbidden. Administrator privileges required.'
        : response.status === 429
        ? 'Too many attempts. Please wait before trying again.'
        : `Request failed with status ${response.status}`
    );
    throw new ApiError(response.status, message, errorData);
  }

  // If 204 No Content
  if (response.status === 204) {
    return {};
  }

  return response.json();
}

export const api = {
  async signup(name, email, password) {
    return request('/api/v1/auth/signup', {
      method: 'POST',
      body: JSON.stringify({ name, email, password }),
    });
  },

  async login(email, password) {
    const res = await request('/api/v1/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    });
    setStoredToken(res.access_token);
    return res;
  },

  async getMe() {
    return request('/api/v1/auth/me', {
      method: 'GET',
    });
  },

  async updateProfile(name) {
    return request('/api/v1/auth/me', {
      method: 'PATCH',
      body: JSON.stringify({ name }),
    });
  },

  async changePassword(currentPassword, newPassword) {
    return request('/api/v1/auth/change-password', {
      method: 'POST',
      body: JSON.stringify({
        current_password: currentPassword,
        new_password: newPassword,
      }),
    });
  },

  async getAdminUsers(limit = 20, offset = 0) {
    return request(`/api/v1/admin/users?limit=${limit}&offset=${offset}`, {
      method: 'GET',
    });
  },

  logout() {
    setStoredToken(null);
  },

  getToken() {
    return getStoredToken();
  },

  downloadFile(path, options) {
    return downloadFile(path, options);
  },
};

export async function downloadFile(path, options = {}) {
  const token = getStoredToken();
  const headers = {
    ...options.headers,
  };

  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  let response;
  try {
    response = await fetch(path, {
      ...options,
      headers,
    });
  } catch {
    throw new ApiError(0, 'Unable to connect to the server. Please check your network connection.');
  }

  if (response.status === 401) {
    setStoredToken(null);
    if (onUnauthorizedCallback) {
      onUnauthorizedCallback();
    }
  }

  if (!response.ok) {
    let errorData = null;
    try {
      errorData = await response.json();
    } catch {
      // Body not JSON
    }
    const message = parseFastAPIError(
      errorData,
      response.status === 401
        ? 'Session expired. Please log in again.'
        : `Request failed with status ${response.status}`
    );
    throw new ApiError(response.status, message, errorData);
  }

  const blob = await response.blob();
  const disposition = response.headers.get('content-disposition');
  return { blob, disposition, headers: response.headers };
}

export { ApiError, request };
