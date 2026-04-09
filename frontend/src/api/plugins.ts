import { apiFetch } from './client';
import type { Plugin, Device, PluginUpdate } from '@/types';

export const fetchPlugins = (signal?: AbortSignal) => apiFetch<Plugin[]>('/api/plugins', { signal });
export const fetchPlugin = (id: string, signal?: AbortSignal) => apiFetch<Plugin>(`/api/plugins/${id}`, { signal });
export const updatePlugin = (id: string, data: PluginUpdate) =>
  apiFetch<Plugin>(`/api/plugins/${id}`, { method: 'PATCH', body: JSON.stringify(data) });
export const fetchPluginDevices = (id: string, signal?: AbortSignal) => apiFetch<Device[]>(`/api/plugins/${id}/devices`, { signal });
