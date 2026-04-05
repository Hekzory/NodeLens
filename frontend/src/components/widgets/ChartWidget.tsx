import { AreaChart } from '@mantine/charts';
import { Text, Center, Loader } from '@mantine/core';
import { useTelemetrySeries } from '@/hooks/telemetry';
import type { Widget } from '@/types';

export function ChartWidget({ widget }: { widget: Widget }) {
  const { data, isLoading } = useTelemetrySeries(widget.sensor_id);

  if (isLoading) return <Center h="100%"><Loader size="sm" /></Center>;
  if (!data?.points.length) return <Center h="100%"><Text c="dimmed" size="sm">No data</Text></Center>;

  const chartData = data.points.map((p) => ({
    time: new Date(p.time).toLocaleTimeString(),
    value: p.value_numeric ?? 0,
  }));

  return (
    <AreaChart
      h="100%"
      data={chartData}
      dataKey="time"
      series={[{ name: 'value', color: 'blue.6' }]}
      curveType="monotone"
      withDots={false}
      withLegend={false}
      tickLine="x"
    />
  );
}
