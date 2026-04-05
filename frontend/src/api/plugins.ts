import { apiFetch } from './client';
import type { Plugin, Device, PluginUpdate } from '@/types';

export const fetchPlugins = () => apiFetch<Plugin[]>('/api/plugins');
export const fetchPlugin = (id: string) => apiFetch<Plugin>(`/api/plugins/${id}`);
export const updatePlugin = (id: string, data: PluginUpdate) =>
  apiFetch<Plugin>(`/api/plugins/${id}`, { method: 'PATCH', body: JSON.stringify(data) });
export const fetchPluginDevices = (id: string) => apiFetch<Device[]>(`/api/plugins/${id}/devices`);
