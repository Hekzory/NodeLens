import { createContext, useContext, useState, useMemo, type ReactNode } from 'react';

export interface TimeRangePreset {
  label: string;
  value: string;
  minutes: number;
}

export const TIME_PRESETS: TimeRangePreset[] = [
  { label: '15m', value: '15m', minutes: 15 },
  { label: '1h', value: '1h', minutes: 60 },
  { label: '6h', value: '6h', minutes: 360 },
  { label: '24h', value: '24h', minutes: 1440 },
  { label: '7d', value: '7d', minutes: 10080 },
];

export interface IntervalOption {
  label: string;
  value: string;
}

/** All available aggregation intervals. */
const ALL_INTERVALS: IntervalOption[] = [
  { label: 'Raw', value: '' },
  { label: '10s', value: '10s' },
  { label: '1m', value: '1m' },
  { label: '15m', value: '15m' },
  { label: '30m', value: '30m' },
  { label: '1h', value: '1h' },
  { label: '6h', value: '6h' },
  { label: '12h', value: '12h' },
  { label: '1d', value: '1d' },
];

/** Map interval value to minutes (0 = raw). */
const INTERVAL_MINUTES: Record<string, number> = {
  '': 0, '10s': 1/6, '1m': 1, '15m': 15, '30m': 30, '1h': 60, '6h': 360, '12h': 720, '1d': 1440,
};

/** Filter intervals that make sense for a given range. An interval should be at most 1/3 of the range. */
export function intervalsForRange(rangeMinutes: number): IntervalOption[] {
  return ALL_INTERVALS.filter((iv) => {
    const m = INTERVAL_MINUTES[iv.value];
    return m === 0 || m <= rangeMinutes / 3;
  });
}

export interface TimeRange {
  preset: string;
  setPreset: (v: string) => void;
  interval: string;
  setInterval: (v: string) => void;
  availableIntervals: IntervalOption[];
  start: string;
  end: string;
  /** Gap threshold in ms — points further apart than this won't be connected */
  gapThresholdMs: number;
}

const TimeRangeContext = createContext<TimeRange | null>(null);

export function TimeRangeProvider({ children }: { children: ReactNode }) {
  const [preset, setPreset] = useState('1h');
  const [interval, setIntervalState] = useState('10s');

  const value = useMemo<TimeRange>(() => {
    const p = TIME_PRESETS.find((t) => t.value === preset) ?? TIME_PRESETS[1];
    const end = new Date();
    const start = new Date(end.getTime() - p.minutes * 60_000);

    const available = intervalsForRange(p.minutes);
    // Reset interval if it's no longer valid for this range
    const effectiveInterval = available.some((iv) => iv.value === interval) ? interval : '';

    // Gap threshold: if aggregating, 3x the interval; otherwise 10min floor scaled with range
    const intervalMs = INTERVAL_MINUTES[effectiveInterval] * 60_000;
    const gapThresholdMs = intervalMs > 0
      ? intervalMs * 3
      : Math.max(10 * 60_000, p.minutes * 60_000 * 0.02);

    return {
      preset,
      setPreset,
      interval: effectiveInterval,
      setInterval: setIntervalState,
      availableIntervals: available,
      start: start.toISOString(),
      end: end.toISOString(),
      gapThresholdMs,
    };
  }, [preset, interval]);

  return (
    <TimeRangeContext.Provider value={value}>
      {children}
    </TimeRangeContext.Provider>
  );
}

export function useTimeRange(): TimeRange {
  const ctx = useContext(TimeRangeContext);
  if (!ctx) throw new Error('useTimeRange must be used within TimeRangeProvider');
  return ctx;
}
