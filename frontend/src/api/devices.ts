import { apiFetch, buildQueryString } from './client';
import type { Device, DeviceDetail, Sensor } from '@/types';

export interface DeviceListParams {
  plugin_id?: string;
  is_online?: boolean;
}

export const fetchDevices = (params?: DeviceListParams) =>
  apiFetch<Device[]>(`/api/devices${buildQueryString({
    plugin_id: params?.plugin_id,
    is_online: params?.is_online,
  })}`);
export const fetchDevice = (id: string) => apiFetch<DeviceDetail>(`/api/devices/${id}`);
export const fetchDeviceSensors = (id: string) => apiFetch<Sensor[]>(`/api/devices/${id}/sensors`);
