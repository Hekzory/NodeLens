import { apiFetch, buildQueryString } from './client';
import type { Device, DeviceDetail, Sensor } from '@/types';

export interface DeviceListParams {
  plugin_id?: string;
  is_online?: boolean;
}

export const fetchDevices = (params?: DeviceListParams, signal?: AbortSignal) =>
  apiFetch<Device[]>(`/api/devices${buildQueryString({
    plugin_id: params?.plugin_id,
    is_online: params?.is_online,
  })}`, { signal });
export const fetchDevice = (id: string, signal?: AbortSignal) => apiFetch<DeviceDetail>(`/api/devices/${id}`, { signal });
export const fetchDeviceSensors = (id: string, signal?: AbortSignal) => apiFetch<Sensor[]>(`/api/devices/${id}/sensors`, { signal });
