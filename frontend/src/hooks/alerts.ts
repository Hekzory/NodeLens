import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  acknowledgeAlert,
  createAlertRule,
  createChannel,
  deleteAlertRule,
  deleteChannel,
  fetchAlertHistory,
  fetchAlertRule,
  fetchAlertRules,
  fetchChannel,
  fetchChannels,
  fetchRuleChannels,
  setRuleChannels,
  updateAlertRule,
  updateChannel,
  type AlertHistoryParams,
  type AlertRuleListParams,
  type ChannelListParams,
} from '@/api/alerts';
import type {
  AlertRuleCreate,
  AlertRuleUpdate,
  NotificationChannelCreate,
  NotificationChannelUpdate,
} from '@/types';

// ── Rules ────────────────────────────────────────────────────────

export const useAlertRules = (params?: AlertRuleListParams) =>
  useQuery({
    queryKey: ['alerts', 'rules', params],
    queryFn: ({ signal }) => fetchAlertRules(params, signal),
  });

export const useAlertRule = (id: string) =>
  useQuery({
    queryKey: ['alerts', 'rules', id],
    queryFn: ({ signal }) => fetchAlertRule(id, signal),
    enabled: !!id,
  });

export const useCreateAlertRule = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: AlertRuleCreate) => createAlertRule(data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['alerts', 'rules'] }),
  });
};

export const useUpdateAlertRule = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: AlertRuleUpdate }) =>
      updateAlertRule(id, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['alerts', 'rules'] }),
  });
};

export const useDeleteAlertRule = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => deleteAlertRule(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['alerts', 'rules'] }),
  });
};

// ── Rule ↔ channel links ────────────────────────────────────────

export const useRuleChannels = (ruleId: string) =>
  useQuery({
    queryKey: ['alerts', 'rules', ruleId, 'channels'],
    queryFn: ({ signal }) => fetchRuleChannels(ruleId, signal),
    enabled: !!ruleId,
  });

export const useSetRuleChannels = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ ruleId, channelIds }: { ruleId: string; channelIds: string[] }) =>
      setRuleChannels(ruleId, channelIds),
    onSuccess: (_data, vars) => {
      qc.invalidateQueries({ queryKey: ['alerts', 'rules'] });
      qc.invalidateQueries({ queryKey: ['alerts', 'rules', vars.ruleId, 'channels'] });
    },
  });
};

// ── History ──────────────────────────────────────────────────────

export const useAlertHistory = (params?: AlertHistoryParams) =>
  useQuery({
    queryKey: ['alerts', 'history', params],
    queryFn: ({ signal }) => fetchAlertHistory(params, signal),
  });

export const useAcknowledgeAlert = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (historyId: string) => acknowledgeAlert(historyId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['alerts', 'history'] }),
  });
};

// ── Channels ─────────────────────────────────────────────────────

export const useChannels = (params?: ChannelListParams) =>
  useQuery({
    queryKey: ['alerts', 'channels', params],
    queryFn: ({ signal }) => fetchChannels(params, signal),
  });

export const useChannel = (id: string) =>
  useQuery({
    queryKey: ['alerts', 'channels', id],
    queryFn: ({ signal }) => fetchChannel(id, signal),
    enabled: !!id,
  });

export const useCreateChannel = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: NotificationChannelCreate) => createChannel(data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['alerts', 'channels'] }),
  });
};

export const useUpdateChannel = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: NotificationChannelUpdate }) =>
      updateChannel(id, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['alerts', 'channels'] }),
  });
};

export const useDeleteChannel = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => deleteChannel(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['alerts', 'channels'] }),
  });
};
