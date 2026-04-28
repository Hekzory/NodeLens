import { apiFetch } from './client';
import type {
  SystemSetting,
  SystemSettingValue,
  SystemSettingsUpdateResponse,
} from '@/types';

export const fetchSystemSettings = (signal?: AbortSignal) =>
  apiFetch<SystemSetting[]>('/api/system/settings', { signal });

export const fetchSystemSetting = (key: string, signal?: AbortSignal) =>
  apiFetch<SystemSetting>(`/api/system/settings/${key}`, { signal });

export const updateSystemSettings = (updates: Record<string, SystemSettingValue>) =>
  apiFetch<SystemSettingsUpdateResponse>('/api/system/settings', {
    method: 'PATCH',
    body: JSON.stringify({ updates }),
  });

export const resetSystemSetting = (key: string) =>
  apiFetch<void>(`/api/system/settings/${key}`, { method: 'DELETE' });
