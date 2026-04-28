import { apiFetch } from './client';
import type { UserCreate, UserRead, UserUpdate } from '@/types';

export const fetchUsers = (signal?: AbortSignal) =>
  apiFetch<UserRead[]>('/api/users', { signal });

export const createUser = (data: UserCreate) =>
  apiFetch<UserRead>('/api/users', {
    method: 'POST',
    body: JSON.stringify(data),
  });

export const updateUser = (id: string, data: UserUpdate) =>
  apiFetch<UserRead>(`/api/users/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  });

export const deleteUser = (id: string) =>
  apiFetch<void>(`/api/users/${id}`, { method: 'DELETE' });

export const adminResetPassword = (id: string, new_password: string) =>
  apiFetch<void>(`/api/users/${id}/password`, {
    method: 'POST',
    body: JSON.stringify({ new_password }),
  });
