import { RingProgress, Text, Center, Stack, Loader } from '@mantine/core';
import { useTelemetryLatest } from '@/hooks/telemetry';
import type { Widget } from '@/types';

export function GaugeWidget({ widget }: { widget: Widget }) {
  const { data, isLoading } = useTelemetryLatest(widget.sensor_id);
  const min = (widget.config.min as number) ?? 0;
  const max = (widget.config.max as number) ?? 100;

  if (isLoading) return <Center h="100%"><Loader size="sm" /></Center>;

  const value = data?.value_numeric ?? 0;
  const pct = Math.min(100, Math.max(0, ((value - min) / (max - min)) * 100));

  return (
    <Center h="100%">
      <RingProgress
        size={120}
        thickness={12}
        sections={[{ value: pct, color: 'blue' }]}
        label={
          <Stack gap={0} align="center">
            <Text fw={700} size="lg" lh={1}>
              {value.toFixed(1)}
            </Text>
            {data?.sensor_name && (
              <Text size="xs" c="dimmed">
                {data.sensor_name}
              </Text>
            )}
          </Stack>
        }
      />
    </Center>
  );
}
