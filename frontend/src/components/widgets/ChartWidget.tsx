import { AreaChart } from '@mantine/charts';
import { Text, Center, Loader } from '@mantine/core';
import { useTelemetrySeries } from '@/hooks/telemetry';
import type { Widget, TelemetryPoint } from '@/types';

/** Detect gaps in time series and insert null-value entries so the chart shows breaks. */
function withGaps(points: TelemetryPoint[]): { time: string; value: number | null }[] {
  if (points.length < 2) {
    return points.map((p) => ({
      time: new Date(p.time).toLocaleTimeString(),
      value: p.value_numeric ?? 0,
    }));
  }

  // Compute median interval between consecutive points
  const intervals: number[] = [];
  for (let i = 1; i < points.length; i++) {
    intervals.push(new Date(points[i].time).getTime() - new Date(points[i - 1].time).getTime());
  }
  intervals.sort((a, b) => a - b);
  const median = intervals[Math.floor(intervals.length / 2)];
  const gapThreshold = median * 3;

  const result: { time: string; value: number | null }[] = [];
  for (let i = 0; i < points.length; i++) {
    if (i > 0) {
      const dt = new Date(points[i].time).getTime() - new Date(points[i - 1].time).getTime();
      if (dt > gapThreshold) {
        // Insert a null point just after the previous point to break the line
        const gapTime = new Date(new Date(points[i - 1].time).getTime() + median);
        result.push({ time: gapTime.toLocaleTimeString(), value: null });
      }
    }
    result.push({
      time: new Date(points[i].time).toLocaleTimeString(),
      value: points[i].value_numeric ?? 0,
    });
  }
  return result;
}

export function ChartWidget({ widget }: { widget: Widget }) {
  const { data, isLoading } = useTelemetrySeries(widget.sensor_id);

  if (isLoading) return <Center h="100%"><Loader size="sm" /></Center>;
  if (!data?.points.length) return <Center h="100%"><Text c="dimmed" size="sm">No data</Text></Center>;

  const chartData = withGaps(data.points);

  return (
    <AreaChart
      h="100%"
      data={chartData}
      dataKey="time"
      series={[{ name: 'value', color: 'blue.6' }]}
      curveType="monotone"
      connectNulls={false}
      withDots={false}
      withLegend={false}
      tickLine="x"
    />
  );
}
