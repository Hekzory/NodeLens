import { RingProgress, Text, Center, Stack, Loader } from '@mantine/core';
import { useTelemetryLatest } from '@/hooks/telemetry';
import type { Widget } from '@/types';

function getGaugeColor(pct: number, config: Widget['config']): string {
  const critical = config.critical as number | undefined;
  const warning = config.warning as number | undefined;
  if (critical !== undefined && pct >= critical) return 'red';
  if (warning !== undefined && pct >= warning) return 'yellow';
  return 'teal';
}

export function GaugeWidget({ widget }: { widget: Widget }) {
  const { data, isLoading } = useTelemetryLatest(widget.sensor_id);
  const min = (widget.config.min as number) ?? 0;
  const max = (widget.config.max as number) ?? 100;
  const unit = (widget.config.unit as string) || '';

  if (isLoading) return <Center h="100%"><Loader size="sm" /></Center>;

  const value = data?.value_numeric ?? 0;
  const pct = Math.min(100, Math.max(0, ((value - min) / (max - min)) * 100));
  const color = getGaugeColor(pct, widget.config);

  return (
    <Center h="100%">
      <RingProgress
        size={140}
        thickness={14}
        roundCaps
        sections={[{ value: pct, color }]}
        label={
          <Stack gap={0} align="center">
            <Text fw={700} size="xl" lh={1}>
              {value.toFixed(1)}
              {unit && <Text component="span" size="xs" c="dimmed" ml={2}>{unit}</Text>}
            </Text>
            {data?.sensor_name && (
              <Text size="xs" c="dimmed" mt={2} lineClamp={1} ta="center" maw={100}>
                {data.sensor_name}
              </Text>
            )}
          </Stack>
        }
      />
    </Center>
  );
}
