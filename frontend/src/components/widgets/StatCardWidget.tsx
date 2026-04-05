import { Stack, Text, Group, Loader, Center } from '@mantine/core';
import { useTelemetryLatest, useTelemetrySummary } from '@/hooks/telemetry';
import { useTimeRange } from '@/context/TimeRange';
import type { Widget } from '@/types';

export function StatCardWidget({ widget }: { widget: Widget }) {
  const { start, end } = useTimeRange();
  const { data, isLoading } = useTelemetryLatest(widget.sensor_id);
  const { data: summary } = useTelemetrySummary(widget.sensor_id, { start, end });

  if (isLoading) return <Center h="100%"><Loader size="sm" /></Center>;

  const value = data?.value_numeric;
  const displayValue = value !== null && value !== undefined ? value.toFixed(2) : '—';

  return (
    <Stack gap="xs" justify="center" h="100%">
      <Text size="xl" fw={700} lh={1}>
        {displayValue}
        {data?.sensor_name && (
          <Text component="span" size="sm" c="dimmed" ml={4}>
            {data.sensor_name}
          </Text>
        )}
      </Text>
      {summary && (
        <Group gap="lg">
          <Text size="xs" c="dimmed">Min: {summary.min?.toFixed(1) ?? '—'}</Text>
          <Text size="xs" c="dimmed">Max: {summary.max?.toFixed(1) ?? '—'}</Text>
          <Text size="xs" c="dimmed">Avg: {summary.avg?.toFixed(1) ?? '—'}</Text>
        </Group>
      )}
      {data?.time && (
        <Text size="xs" c="dimmed">{new Date(data.time).toLocaleString()}</Text>
      )}
    </Stack>
  );
}
