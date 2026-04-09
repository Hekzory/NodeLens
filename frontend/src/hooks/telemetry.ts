import { useQuery } from '@tanstack/react-query';
import {
  fetchTelemetrySeries,
  fetchTelemetryLatest,
  fetchTelemetrySummary,
  fetchDeviceTelemetry,
  type TelemetryParams,
} from '@/api/telemetry';

const POLL = 10_000;

export const useTelemetrySeries = (
  sensorId: string | null | undefined,
  params?: TelemetryParams,
) =>
  useQuery({
    queryKey: ['telemetry', sensorId, 'series', params?.start, params?.end, params?.interval],
    queryFn: ({ signal }) => fetchTelemetrySeries(sensorId!, params, signal),
    enabled: !!sensorId,
    refetchInterval: POLL,
  });

export const useTelemetryLatest = (sensorId: string | null | undefined) =>
  useQuery({
    queryKey: ['telemetry', sensorId, 'latest'],
    queryFn: ({ signal }) => fetchTelemetryLatest(sensorId!, signal),
    enabled: !!sensorId,
    refetchInterval: POLL,
  });

export const useTelemetrySummary = (
  sensorId: string | null | undefined,
  params?: TelemetryParams,
) =>
  useQuery({
    queryKey: ['telemetry', sensorId, 'summary', params?.start, params?.end],
    queryFn: ({ signal }) => fetchTelemetrySummary(sensorId!, params, signal),
    enabled: !!sensorId,
    refetchInterval: POLL,
  });

export const useDeviceTelemetry = (deviceId: string) =>
  useQuery({
    queryKey: ['telemetry', 'device', deviceId],
    queryFn: ({ signal }) => fetchDeviceTelemetry(deviceId, signal),
    enabled: !!deviceId,
    refetchInterval: POLL,
  });
