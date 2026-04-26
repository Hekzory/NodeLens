import { useState, useMemo, useCallback, useEffect, type ReactNode } from 'react';
import {
  TIME_PRESETS,
  INTERVAL_MINUTES,
  TimeRangeContext,
  intervalsForRange,
  loadSaved,
  saveToDisk,
  type TimeRange,
} from './timeRangeContext';

export function TimeRangeProvider({ dashboardId, children }: { dashboardId: string; children: ReactNode }) {
  const [preset, setPresetRaw] = useState(() => loadSaved(dashboardId)?.preset ?? '1h');
  const [interval, setIntervalRaw] = useState(() => loadSaved(dashboardId)?.interval ?? '10s');

  const setPreset = useCallback((v: string) => {
    setPresetRaw(v);
    saveToDisk(dashboardId, v, interval);
  }, [dashboardId, interval]);

  const setInterval = useCallback((v: string) => {
    setIntervalRaw(v);
    saveToDisk(dashboardId, preset, v);
  }, [dashboardId, preset]);

  // Tick `nowMs` so the rolling window slides forward without user action.
  const [nowMs, setNowMs] = useState(() => Date.now());
  useEffect(() => {
    const id = window.setInterval(() => setNowMs(Date.now()), 30_000);
    return () => window.clearInterval(id);
  }, []);

  const value = useMemo<TimeRange>(() => {
    const p = TIME_PRESETS.find((t) => t.value === preset) ?? TIME_PRESETS[1];
    const end = new Date(nowMs);
    const start = new Date(nowMs - p.minutes * 60_000);

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
      setInterval,
      availableIntervals: available,
      start: start.toISOString(),
      end: end.toISOString(),
      gapThresholdMs,
    };
  }, [preset, interval, setPreset, setInterval, nowMs]);

  return (
    <TimeRangeContext.Provider value={value}>
      {children}
    </TimeRangeContext.Provider>
  );
}
