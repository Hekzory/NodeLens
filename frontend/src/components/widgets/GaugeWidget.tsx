import { RingProgress, Text, Center, Stack, Skeleton } from '@mantine/core';
import { useElementSize } from '@mantine/hooks';
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
  const { ref, width, height } = useElementSize();

  if (!widget.sensor_id) return <Center h="100%"><Text c="dimmed" size="sm">No sensor configured</Text></Center>;

  const min = (widget.config.min as number) ?? 0;
  const max = (widget.config.max as number) ?? 100;
  const unit = (widget.config.unit as string) || '';

  if (isLoading) return <Skeleton h="100%" />;

  const value = data?.value_numeric ?? 0;
  const pct = Math.min(100, Math.max(0, ((value - min) / (max - min)) * 100));
  const color = getGaugeColor(pct, widget.config);

  // Fit the ring to the smaller of the available dimensions, so the gauge
  // grows with the widget instead of sitting in a tiny 140px puck.
  const dim = Math.min(width, height);
  const ringSize = Math.min(280, Math.max(112, Math.floor(dim) - 8));
  const thickness = Math.max(10, Math.round(ringSize / 14));
  const valueFs = Math.max(18, Math.min(32, Math.round(ringSize * 0.135)));
  const unitFs = Math.max(11, Math.round(valueFs * 0.5));
  const labelMaxW = Math.max(80, ringSize - thickness * 4);

  return (
    <div
      ref={ref}
      style={{ height: '100%', width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}
    >
      {dim > 0 && (
        <RingProgress
          size={ringSize}
          thickness={thickness}
          roundCaps
          sections={[{ value: pct, color }]}
          label={
            <Stack gap={2} align="center">
              <Text
                fw={700}
                className="nl-mono"
                lh={1}
                style={{ fontSize: valueFs, letterSpacing: '-0.01em' }}
              >
                {value.toFixed(1)}
                {unit && (
                  <Text component="span" c="dimmed" ml={2} ff="var(--font-sans)" style={{ fontSize: unitFs }}>
                    {unit}
                  </Text>
                )}
              </Text>
              {data?.sensor_name && (
                <Text size="xs" c="dimmed" lineClamp={1} ta="center" maw={labelMaxW}>
                  {data.sensor_name}
                </Text>
              )}
            </Stack>
          }
        />
      )}
    </div>
  );
}
