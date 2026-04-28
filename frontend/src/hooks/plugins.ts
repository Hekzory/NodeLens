import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  fetchPlugins,
  fetchPlugin,
  updatePlugin,
  fetchPluginDevices,
  fetchPluginConfig,
  updatePluginConfig,
  resetPluginConfig,
} from '@/api/plugins';
import type { PluginConfigValue } from '@/types';

export const usePlugins = () =>
  useQuery({ queryKey: ['plugins'], queryFn: ({ signal }) => fetchPlugins(signal) });

export const usePlugin = (id: string) =>
  useQuery({ queryKey: ['plugins', id], queryFn: ({ signal }) => fetchPlugin(id, signal), enabled: !!id });

export const usePluginDevices = (id: string) =>
  useQuery({
    queryKey: ['plugins', id, 'devices'],
    queryFn: ({ signal }) => fetchPluginDevices(id, signal),
    enabled: !!id,
  });

export const useTogglePlugin = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, isActive }: { id: string; isActive: boolean }) =>
      updatePlugin(id, { is_active: isActive }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['plugins'] }),
  });
};

export const usePluginConfig = (id: string) =>
  useQuery({
    queryKey: ['plugins', id, 'config'],
    queryFn: ({ signal }) => fetchPluginConfig(id, signal),
    enabled: !!id,
    refetchInterval: false,
    staleTime: 60_000,
  });

export const useUpdatePluginConfig = (id: string) => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (updates: Record<string, PluginConfigValue>) =>
      updatePluginConfig(id, updates),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['plugins', id, 'config'] }),
  });
};

export const useResetPluginConfig = (id: string) => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (key?: string) => resetPluginConfig(id, key),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['plugins', id, 'config'] }),
  });
};
