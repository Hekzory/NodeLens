import { useQuery } from '@tanstack/react-query';
import { fetchDevices, fetchDevice, fetchDeviceSensors } from '@/api/devices';
import type { DeviceListParams } from '@/api/devices';

export const useDevices = (params?: DeviceListParams) =>
  useQuery({ queryKey: ['devices', params], queryFn: () => fetchDevices(params) });

export const useDevice = (id: string) =>
  useQuery({ queryKey: ['devices', id], queryFn: () => fetchDevice(id), enabled: !!id });

export const useDeviceSensors = (id: string) =>
  useQuery({
    queryKey: ['devices', id, 'sensors'],
    queryFn: () => fetchDeviceSensors(id),
    enabled: !!id,
  });
