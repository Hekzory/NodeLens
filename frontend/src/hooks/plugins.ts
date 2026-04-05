import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { fetchPlugins, fetchPlugin, updatePlugin, fetchPluginDevices } from '@/api/plugins';

export const usePlugins = () =>
  useQuery({ queryKey: ['plugins'], queryFn: fetchPlugins });

export const usePlugin = (id: string) =>
  useQuery({ queryKey: ['plugins', id], queryFn: () => fetchPlugin(id), enabled: !!id });

export const usePluginDevices = (id: string) =>
  useQuery({
    queryKey: ['plugins', id, 'devices'],
    queryFn: () => fetchPluginDevices(id),
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
