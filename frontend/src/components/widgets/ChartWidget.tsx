import { useMemo } from 'react';
import { AreaChart } from '@mantine/charts';
import { Text, Center, Skeleton } from '@mantine/core';
import { useTelemetrySeries } from '@/hooks/telemetry';
import { useTimeRange } from '@/context/timeRangeContext';
import type { Widget, TelemetryPoint } from '@/types';

interface ChartPoint {
  _ts: number;
  value: number | null;
}

/** Format tick label based on range duration. */
function formatTick(ts: number, rangeMinutes: number, withSeconds = false): string {
  const d = new Date(ts);
  const timeOpts: Intl.DateTimeFormatOptions = withSeconds
    ? { hour: '2-digit', minute: '2-digit', second: '2-digit' }
    : { hour: '2-digit', minute: '2-digit' };
  if (rangeMinutes <= 360) {
    return d.toLocaleTimeString([], timeOpts);
  }
  return d.toLocaleDateString([], { month: 'numeric', day: 'numeric' }) +
    ' ' + d.toLocaleTimeString([], timeOpts);
}

/**
 * Build chart data with numeric timestamps for proportional X-axis placement.
 * - Always includes boundary points at window start/end
 * - Inserts null at gaps so the line breaks visually
 */
function buildChartData(
  points: TelemetryPoint[],
  startMs: number,
  endMs: number,
  gapThresholdMs: number,
): ChartPoint[] {
  const result: ChartPoint[] = [];

  // Always add window start boundary
  result.push({ _ts: startMs, value: null });

  for (let i = 0; i < points.length; i++) {
    const ts = new Date(points[i].time).getTime();
    const prevTs = i > 0
      ? new Date(points[i - 1].time).getTime()
      : startMs;

    if (ts - prevTs > gapThresholdMs) {
      // Insert null just after the previous real point to break the line
      if (i > 0) {
        result.push({ _ts: prevTs + 1, value: null });
      }
      // Insert null just before this point to keep the gap visible
      result.push({ _ts: ts - 1, value: null });
    }

    result.push({ _ts: ts, value: points[i].value_numeric });
  }

  // Always add window end boundary
  result.push({ _ts: endMs, value: null });

  return result;
}

function buildTicks(startMs: number, endMs: number, count: number): number[] {
  const step = (endMs - startMs) / (count - 1);
  return Array.from({ length: count }, (_, i) => Math.round(startMs + i * step));
}

export function ChartWidget({ widget }: { widget: Widget }) {
  const { start, end, gapThresholdMs, interval } = useTimeRange();
  const startMs = new Date(start).getTime();
  const endMs = new Date(end).getTime();
  const rangeMinutes = (endMs - startMs) / 60_000;

  const params = useMemo(() => ({
    start,
    end,
    ...(interval ? { interval } : {}),
  }), [start, end, interval]);

  const { data, isLoading } = useTelemetrySeries(widget.sensor_id, params);

  const chartData = useMemo(() => {
    if (!data?.points.length) return [];
    return buildChartData(data.points, startMs, endMs, gapThresholdMs);
  }, [data, startMs, endMs, gapThresholdMs]);

  if (!widget.sensor_id) return <Center h="100%"><Text c="dimmed" size="sm">No sensor configured</Text></Center>;
  if (isLoading) return <Skeleton h="100%" />;
  if (!chartData.length) return <Center h="100%"><Text c="dimmed" size="sm">No data for this range</Text></Center>;

  return (
    <AreaChart
      h="100%"
      data={chartData}
      dataKey="_ts"
      series={[{ name: 'value', color: 'cyan.6' }]}
      curveType="monotone"
      connectNulls={false}
      withDots={chartData.filter((p) => p.value !== null).length < 60}
      dotProps={{ r: 1.5 }}
      withLegend={false}
      tickLine="xy"
      gridAxis="xy"
      xAxisProps={{
        type: 'number' as const,
        domain: [startMs, endMs],
        ticks: buildTicks(startMs, endMs, 6),
        tickFormatter: (ts: number) => formatTick(ts, rangeMinutes),
        scale: 'time',
      }}
      yAxisProps={{
        domain: ['auto', 'auto'],
        tickCount: 5,
        width: 50,
      }}
      tooltipProps={{
        content: ({ payload }) => {
          if (!payload?.length) return null;
          const p = payload[0].payload;
          const val = p.value;
          if (val === null || val === undefined) return null;
          return (
            <div style={{
              background: 'var(--surface-tooltip)',
              border: '1px solid var(--border-1)',
              borderRadius: 'var(--radius-sm)',
              padding: '6px 10px',
              fontSize: 12,
            }}>
              <div className="nl-mono" style={{ color: 'var(--fg-3)' }}>
                {formatTick(p._ts, rangeMinutes, true)}
              </div>
              <div className="nl-mono" style={{ fontWeight: 600, color: 'var(--fg-1)' }}>
                {Number(val).toFixed(2)}
              </div>
            </div>
          );
        },
      }}
    />
  );
}
