import { apiFetch } from './client';
import type { TelemetrySeries, TelemetryLatest, TelemetrySummary, DeviceTelemetry } from '@/types';

export interface TelemetryParams {
  start?: string;
  end?: string;
  limit?: number;
  interval?: string;
}

const qs = (params?: TelemetryParams) => {
  const q = new URLSearchParams();
  if (params?.start) q.set('start', params.start);
  if (params?.end) q.set('end', params.end);
  if (params?.limit) q.set('limit', String(params.limit));
  if (params?.interval) q.set('interval', params.interval);
  return q.toString() ? `?${q}` : '';
};

export const fetchTelemetrySeries = (sensorId: string, params?: TelemetryParams) =>
  apiFetch<TelemetrySeries>(`/api/telemetry/${sensorId}${qs(params)}`);

export const fetchTelemetryLatest = (sensorId: string) =>
  apiFetch<TelemetryLatest>(`/api/telemetry/${sensorId}/latest`);

export const fetchTelemetrySummary = (sensorId: string, params?: TelemetryParams) =>
  apiFetch<TelemetrySummary>(`/api/telemetry/${sensorId}/summary${qs(params)}`);

export const fetchDeviceTelemetry = (deviceId: string) =>
  apiFetch<DeviceTelemetry>(`/api/telemetry/device/${deviceId}`);
