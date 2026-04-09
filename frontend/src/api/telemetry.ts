import { apiFetch, buildQueryString } from './client';
import type { TelemetrySeries, TelemetryLatest, TelemetrySummary, DeviceTelemetry } from '@/types';

export interface TelemetryParams {
  start?: string;
  end?: string;
  limit?: number;
  interval?: string;
}

export const fetchTelemetrySeries = (sensorId: string, params?: TelemetryParams, signal?: AbortSignal) =>
  apiFetch<TelemetrySeries>(`/api/telemetry/${sensorId}${buildQueryString({ ...params })}`, { signal });

export const fetchTelemetryLatest = (sensorId: string, signal?: AbortSignal) =>
  apiFetch<TelemetryLatest>(`/api/telemetry/${sensorId}/latest`, { signal });

export const fetchTelemetrySummary = (sensorId: string, params?: TelemetryParams, signal?: AbortSignal) =>
  apiFetch<TelemetrySummary>(`/api/telemetry/${sensorId}/summary${buildQueryString({ ...params })}`, { signal });

export const fetchDeviceTelemetry = (deviceId: string, signal?: AbortSignal) =>
  apiFetch<DeviceTelemetry>(`/api/telemetry/device/${deviceId}`, { signal });
