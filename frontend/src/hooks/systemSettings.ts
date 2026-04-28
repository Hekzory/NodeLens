import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  fetchSystemSettings,
  resetSystemSetting,
  updateSystemSettings,
} from '@/api/systemSettings';
import { applyPollingInterval } from '@/lib/queryClient';
import type { SystemSettingValue, SystemSettingsUpdateResponse } from '@/types';

const QK = ['system', 'settings'] as const;

export const useSystemSettings = () =>
  useQuery({
    queryKey: QK,
    queryFn: ({ signal }) => fetchSystemSettings(signal),
    // Settings rarely change; don't poll on the standard 10s cadence.
    refetchInterval: false,
    staleTime: 60_000,
  });

const handlePollingInterval = (resp: SystemSettingsUpdateResponse) => {
  const polling = resp.updated.find(
    (s) => s.key === 'frontend_polling_interval_seconds',
  );
  if (polling && typeof polling.value === 'number') {
    applyPollingInterval(polling.value);
  }
};

export const useUpdateSystemSettings = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (updates: Record<string, SystemSettingValue>) =>
      updateSystemSettings(updates),
    onSuccess: (resp) => {
      handlePollingInterval(resp);
      qc.invalidateQueries({ queryKey: QK });
    },
  });
};

export const useResetSystemSetting = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (key: string) => resetSystemSetting(key),
    onSuccess: () => qc.invalidateQueries({ queryKey: QK }),
  });
};
