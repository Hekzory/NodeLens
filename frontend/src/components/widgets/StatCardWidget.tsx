import { Stack, Text, Group, Loader, Center } from '@mantine/core';
import { IconTrendingUp, IconTrendingDown, IconMinus } from '@tabler/icons-react';
import { useTelemetryLatest, useTelemetrySummary } from '@/hooks/telemetry';
import { useTimeRange } from '@/context/TimeRange';
import type { Widget } from '@/types';

function formatTime(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

export function StatCardWidget({ widget }: { widget: Widget }) {
  const { start, end } = useTimeRange();
  const { data, isLoading } = useTelemetryLatest(widget.sensor_id);
  const { data: summary } = useTelemetrySummary(widget.sensor_id, { start, end });
  const unit = (widget.config.unit as string) || '';

  if (isLoading) return <Center h="100%"><Loader size="sm" /></Center>;

  const value = data?.value_numeric;
  const hasValue = value !== null && value !== undefined;
  const displayValue = hasValue ? value.toFixed(2) : '—';

  // Trend relative to average
  const avg = summary?.avg;
  const delta = hasValue && avg != null && avg !== 0
    ? ((value - avg) / Math.abs(avg)) * 100
    : null;

  return (
    <Stack gap={6} justify="center" h="100%">
      <Group gap={6} align="baseline" wrap="nowrap">
        <Text size="xl" fw={700} lh={1}>
          {displayValue}
        </Text>
        {unit && <Text size="sm" c="dimmed" lh={1}>{unit}</Text>}
        {delta !== null && (
          <Group gap={2} wrap="nowrap" ml={4}>
            {delta > 1 ? (
              <IconTrendingUp size={14} color="var(--mantine-color-dimmed)" />
            ) : delta < -1 ? (
              <IconTrendingDown size={14} color="var(--mantine-color-dimmed)" />
            ) : (
              <IconMinus size={14} color="var(--mantine-color-dimmed)" />
            )}
            <Text size="xs" c="dimmed" lh={1}>
              {Math.abs(delta).toFixed(1)}%
            </Text>
          </Group>
        )}
      </Group>
      {summary && (
        <Group gap="sm">
          <Text size="xs" c="dimmed">Min {summary.min?.toFixed(1) ?? '—'}</Text>
          <Text size="xs" c="dimmed">Avg {summary.avg?.toFixed(1) ?? '—'}</Text>
          <Text size="xs" c="dimmed">Max {summary.max?.toFixed(1) ?? '—'}</Text>
        </Group>
      )}
      {data?.time && (
        <Text size="xs" c="dimmed">{formatTime(data.time)}</Text>
      )}
    </Stack>
  );
}
