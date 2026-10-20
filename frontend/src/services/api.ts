import type { TokenResponse, User, UserListResponse } from '../types/auth';

const TOKEN_KEY = 'qa_auth_token';

class ApiError extends Error {
  status: number;
  data: any;

  constructor(status: number, message: string, data?: any) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.data = data;
  }
}

function getStoredToken(): string | null {
  return sessionStorage.getItem(TOKEN_KEY);
}

export function setStoredToken(token: string | null): void {
  if (token) {
    sessionStorage.setItem(TOKEN_KEY, token);
  } else {
    sessionStorage.removeItem(TOKEN_KEY);
  }
}

function parseFastAPIError(data: any, fallbackMessage: string): string {
  if (!data) return fallbackMessage;
  if (typeof data === 'string') return data;
  if (typeof data.detail === 'string') return data.detail;
  if (Array.isArray(data.detail)) {
    // Array of pydantic errors: [{ loc: [...], msg: "..." }]
    const messages = data.detail.map((err: any) => {
      const field = Array.isArray(err.loc) ? err.loc[err.loc.length - 1] : '';
      const cleanField = field && field !== 'body' ? `${field}: ` : '';
      return `${cleanField}${err.msg || 'Invalid field'}`;
    });
    return messages.join('. ');
  }
  return fallbackMessage;
}

let onUnauthorizedCallback: (() => void) | null = null;

export function setOnUnauthorizedCallback(cb: () => void) {
  onUnauthorizedCallback = cb;
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getStoredToken();
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string>),
  };

  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  let response: Response;
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
    let errorData: any = null;
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
    return {} as T;
  }

  return response.json();
}

export const api = {
  async signup(name: string, email: string, password: string): Promise<User> {
    return request<User>('/api/v1/auth/signup', {
      method: 'POST',
      body: JSON.stringify({ name, email, password }),
    });
  },

  async login(email: string, password: string): Promise<TokenResponse> {
    const res = await request<TokenResponse>('/api/v1/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    });
    setStoredToken(res.access_token);
    return res;
  },

  async getMe(): Promise<User> {
    return request<User>('/api/v1/auth/me', {
      method: 'GET',
    });
  },

  async updateProfile(name: string): Promise<User> {
    return request<User>('/api/v1/auth/me', {
      method: 'PATCH',
      body: JSON.stringify({ name }),
    });
  },

  async changePassword(currentPassword: string, newPassword: string): Promise<{ message: string }> {
    return request<{ message: string }>('/api/v1/auth/change-password', {
      method: 'POST',
      body: JSON.stringify({
        current_password: currentPassword,
        new_password: newPassword,
      }),
    });
  },

  async getAdminUsers(limit = 20, offset = 0): Promise<UserListResponse> {
    return request<UserListResponse>(`/api/v1/admin/users?limit=${limit}&offset=${offset}`, {
      method: 'GET',
    });
  },

  logout(): void {
    setStoredToken(null);
  },

  getToken(): string | null {
    return getStoredToken();
  },
};

export { ApiError };
