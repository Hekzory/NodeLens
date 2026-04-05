import { apiFetch } from './client';
import type { Device, DeviceDetail, Sensor } from '@/types';

export interface DeviceListParams {
  plugin_id?: string;
  is_online?: boolean;
}

export const fetchDevices = (params?: DeviceListParams) => {
  const qs = new URLSearchParams();
  if (params?.plugin_id) qs.set('plugin_id', params.plugin_id);
  if (params?.is_online !== undefined) qs.set('is_online', String(params.is_online));
  const query = qs.toString() ? `?${qs}` : '';
  return apiFetch<Device[]>(`/api/devices${query}`);
};
export const fetchDevice = (id: string) => apiFetch<DeviceDetail>(`/api/devices/${id}`);
export const fetchDeviceSensors = (id: string) => apiFetch<Sensor[]>(`/api/devices/${id}/sensors`);
