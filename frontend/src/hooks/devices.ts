import { useQuery } from '@tanstack/react-query';
import { fetchDevices, fetchDevice, fetchDeviceSensors } from '@/api/devices';
import type { DeviceListParams } from '@/api/devices';

export const useDevices = (params?: DeviceListParams) =>
  useQuery({ queryKey: ['devices', params?.plugin_id, params?.is_online], queryFn: ({ signal }) => fetchDevices(params, signal) });

export const useDevice = (id: string) =>
  useQuery({ queryKey: ['devices', id], queryFn: ({ signal }) => fetchDevice(id, signal), enabled: !!id });

export const useDeviceSensors = (id: string) =>
  useQuery({
    queryKey: ['devices', id, 'sensors'],
    queryFn: ({ signal }) => fetchDeviceSensors(id, signal),
    enabled: !!id,
  });
