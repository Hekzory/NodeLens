import { apiFetch, buildQueryString } from './client';
import type { TelemetrySeries, TelemetryLatest, TelemetrySummary, DeviceTelemetry } from '@/types';

export interface TelemetryParams {
  start?: string;
  end?: string;
  limit?: number;
  interval?: string;
}

export const fetchTelemetrySeries = (sensorId: string, params?: TelemetryParams) =>
  apiFetch<TelemetrySeries>(`/api/telemetry/${sensorId}${buildQueryString({ ...params })}`);

export const fetchTelemetryLatest = (sensorId: string) =>
  apiFetch<TelemetryLatest>(`/api/telemetry/${sensorId}/latest`);

export const fetchTelemetrySummary = (sensorId: string, params?: TelemetryParams) =>
  apiFetch<TelemetrySummary>(`/api/telemetry/${sensorId}/summary${buildQueryString({ ...params })}`);

export const fetchDeviceTelemetry = (deviceId: string) =>
  apiFetch<DeviceTelemetry>(`/api/telemetry/device/${deviceId}`);
