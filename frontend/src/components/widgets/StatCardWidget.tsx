import { Stack, Text, Group, Skeleton, Center } from '@mantine/core';
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

  if (!widget.sensor_id) return <Center h="100%"><Text c="dimmed" size="sm">No sensor configured</Text></Center>;

  const unit = (widget.config.unit as string) || '';

  if (isLoading) return <Skeleton h="100%" />;

  const numeric = data?.value_numeric;
  const text = data?.value_text;
  const hasNumeric = numeric != null;
  const displayValue = hasNumeric ? numeric.toFixed(2) : (text ?? '—');

  const avg = summary?.avg;
  const delta = hasNumeric && avg != null && avg !== 0
    ? ((numeric - avg) / Math.abs(avg)) * 100
    : null;

  return (
    <Stack gap={8} justify="center" h="100%">
      <Group gap={6} align="baseline" wrap="nowrap">
        <Text
          ff="var(--font-mono)"
          fw={700}
          lh={1}
          style={{ fontSize: 28, fontVariantNumeric: 'tabular-nums', letterSpacing: '-0.01em' }}
        >
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
            <Text size="xs" c="dimmed" lh={1} ff="var(--font-mono)" style={{ fontVariantNumeric: 'tabular-nums' }}>
              {Math.abs(delta).toFixed(1)}%
            </Text>
          </Group>
        )}
      </Group>
      {summary && (
        <Group gap="md">
          <Text size="xs" c="dimmed">
            Min <Text component="span" ff="var(--font-mono)" style={{ fontVariantNumeric: 'tabular-nums' }} c="dimmed">{summary.min?.toFixed(1) ?? '—'}</Text>
          </Text>
          <Text size="xs" c="dimmed">
            Avg <Text component="span" ff="var(--font-mono)" style={{ fontVariantNumeric: 'tabular-nums' }} c="dimmed">{summary.avg?.toFixed(1) ?? '—'}</Text>
          </Text>
          <Text size="xs" c="dimmed">
            Max <Text component="span" ff="var(--font-mono)" style={{ fontVariantNumeric: 'tabular-nums' }} c="dimmed">{summary.max?.toFixed(1) ?? '—'}</Text>
          </Text>
        </Group>
      )}
      {data?.time && (
        <Text size="xs" c="dimmed" ff="var(--font-mono)" style={{ fontVariantNumeric: 'tabular-nums' }}>
          {formatTime(data.time)}
        </Text>
      )}
    </Stack>
  );
}
