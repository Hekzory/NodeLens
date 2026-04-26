import { createContext, useContext } from 'react';

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
export const INTERVAL_MINUTES: Record<string, number> = {
  '': 0, '10s': 1/6, '1m': 1, '15m': 15, '30m': 30, '1h': 60, '6h': 360, '12h': 720, '1d': 1440,
};

/** Filter intervals that make sense for a given range. An interval should be at most 1/3 of the range. */
export function intervalsForRange(rangeMinutes: number): IntervalOption[] {
  return ALL_INTERVALS.filter((iv) => {
    const m = INTERVAL_MINUTES[iv.value];
    return m === 0 || m <= rangeMinutes / 3;
  });
}

const STORAGE_KEY_PREFIX = 'nodelens:timerange:';

export function loadSaved(dashboardId: string): { preset: string; interval: string } | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY_PREFIX + dashboardId);
    if (!raw) return null;
    return JSON.parse(raw);
  } catch { return null; }
}

export function saveToDisk(dashboardId: string, preset: string, interval: string) {
  try {
    localStorage.setItem(STORAGE_KEY_PREFIX + dashboardId, JSON.stringify({ preset, interval }));
  } catch { /* quota exceeded — ignore */ }
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

export const TimeRangeContext = createContext<TimeRange | null>(null);

export function useTimeRange(): TimeRange {
  const ctx = useContext(TimeRangeContext);
  if (!ctx) throw new Error('useTimeRange must be used within TimeRangeProvider');
  return ctx;
}
