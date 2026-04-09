import { Stack, Text, ThemeIcon, Center } from '@mantine/core';
import { IconCircleCheck, IconCircleX, IconCircleDashed } from '@tabler/icons-react';
import { useTelemetryLatest } from '@/hooks/telemetry';
import type { Widget } from '@/types';

const STALE_MS = 60_000;

function isTimestampRecent(time: string | null | undefined, asOf: number): boolean {
  if (!time || !asOf) return false;
  return asOf - new Date(time).getTime() < STALE_MS;
}

export function StatusWidget({ widget }: { widget: Widget }) {
  const { data, dataUpdatedAt } = useTelemetryLatest(widget.sensor_id);

  if (!widget.sensor_id) {
    return (
      <Center h="100%">
        <Text c="dimmed" size="sm">No sensor configured</Text>
      </Center>
    );
  }

  const isRecent = isTimestampRecent(data?.time, dataUpdatedAt);
  const hasData = data?.value_numeric !== null && data?.value_numeric !== undefined;
  const ok = isRecent && hasData;

  return (
    <Center h="100%">
      <Stack align="center" gap={4}>
        <ThemeIcon color={ok ? 'green' : isRecent ? 'yellow' : 'red'} variant="light" size="xl">
          {ok ? <IconCircleCheck /> : isRecent ? <IconCircleDashed /> : <IconCircleX />}
        </ThemeIcon>
        <Text size="sm" fw={500}>{data?.sensor_name ?? '—'}</Text>
        <Text size="xs" c="dimmed">{ok ? 'Online' : 'No data'}</Text>
      </Stack>
    </Center>
  );
}
