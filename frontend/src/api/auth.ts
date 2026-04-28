import { apiFetch } from './client';
import type { AuthStatus, UserRead } from '@/types';

export const fetchAuthStatus = (signal?: AbortSignal) =>
  apiFetch<AuthStatus>('/api/auth/status', { signal });

export const fetchMe = (signal?: AbortSignal) =>
  apiFetch<UserRead>('/api/auth/me', { signal });

export const login = (username: string, password: string) =>
  apiFetch<UserRead>('/api/auth/login', {
    method: 'POST',
    body: JSON.stringify({ username, password }),
  });

export const setup = (username: string, password: string) =>
  apiFetch<UserRead>('/api/auth/setup', {
    method: 'POST',
    body: JSON.stringify({ username, password }),
  });

export const logout = () =>
  apiFetch<void>('/api/auth/logout', { method: 'POST' });

export const changePassword = (old_password: string, new_password: string) =>
  apiFetch<void>('/api/auth/password', {
    method: 'POST',
    body: JSON.stringify({ old_password, new_password }),
  });
