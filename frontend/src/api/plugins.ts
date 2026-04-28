import { apiFetch, buildQueryString } from './client';
import type {
  Plugin,
  Device,
  PluginUpdate,
  PluginConfig,
  PluginConfigUpdateResponse,
  PluginConfigValue,
} from '@/types';

export const fetchPlugins = (signal?: AbortSignal) => apiFetch<Plugin[]>('/api/plugins', { signal });
export const fetchPlugin = (id: string, signal?: AbortSignal) => apiFetch<Plugin>(`/api/plugins/${id}`, { signal });
export const updatePlugin = (id: string, data: PluginUpdate) =>
  apiFetch<Plugin>(`/api/plugins/${id}`, { method: 'PATCH', body: JSON.stringify(data) });
export const fetchPluginDevices = (id: string, signal?: AbortSignal) => apiFetch<Device[]>(`/api/plugins/${id}/devices`, { signal });

export const fetchPluginConfig = (id: string, signal?: AbortSignal) =>
  apiFetch<PluginConfig>(`/api/plugins/${id}/config`, { signal });

export const updatePluginConfig = (
  id: string,
  updates: Record<string, PluginConfigValue>,
) =>
  apiFetch<PluginConfigUpdateResponse>(`/api/plugins/${id}/config`, {
    method: 'PATCH',
    body: JSON.stringify({ updates }),
  });

export const resetPluginConfig = (id: string, key?: string) =>
  apiFetch<void>(
    `/api/plugins/${id}/config${buildQueryString({ key })}`,
    { method: 'DELETE' },
  );
