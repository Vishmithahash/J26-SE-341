export type UserRole = 'ADMIN' | 'USER';

export interface User {
  id: number;
  name: string;
  email: string;
  role: UserRole;
  is_active: boolean;
  created_at_utc: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: User;
}

export interface UserListResponse {
  items: User[];
  total: number;
  limit: number;
  offset: number;
}

export interface ModelPreference {
  connectionType: 'local' | 'hosted';
  provider: 'ollama' | 'openai-compatible' | 'custom';
  modelId: string;
  updatedAt?: string;
}

export type ThemeMode = 'light' | 'dark' | 'system';
export type DisplayDensity = 'comfortable' | 'compact';
