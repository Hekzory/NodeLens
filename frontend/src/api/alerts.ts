import { apiFetch, buildQueryString } from './client';
import type {
  AlertHistory,
  AlertRule,
  AlertRuleCreate,
  AlertRuleUpdate,
  NotificationChannel,
  NotificationChannelCreate,
  NotificationChannelUpdate,
} from '@/types';

// ── Alert rules ──────────────────────────────────────────────────

export interface AlertRuleListParams {
  is_active?: boolean;
  severity?: string;
}

export const fetchAlertRules = (params?: AlertRuleListParams, signal?: AbortSignal) =>
  apiFetch<AlertRule[]>(`/api/alerts/rules${buildQueryString({
    is_active: params?.is_active,
    severity: params?.severity,
  })}`, { signal });

export const fetchAlertRule = (id: string, signal?: AbortSignal) =>
  apiFetch<AlertRule>(`/api/alerts/rules/${id}`, { signal });

export const createAlertRule = (data: AlertRuleCreate) =>
  apiFetch<AlertRule>('/api/alerts/rules', { method: 'POST', body: JSON.stringify(data) });

export const updateAlertRule = (id: string, data: AlertRuleUpdate) =>
  apiFetch<AlertRule>(`/api/alerts/rules/${id}`, { method: 'PATCH', body: JSON.stringify(data) });

export const deleteAlertRule = (id: string) =>
  apiFetch<void>(`/api/alerts/rules/${id}`, { method: 'DELETE' });

// ── Rule ↔ channel links ────────────────────────────────────────

export const fetchRuleChannels = (ruleId: string, signal?: AbortSignal) =>
  apiFetch<NotificationChannel[]>(`/api/alerts/rules/${ruleId}/channels`, { signal });

export const setRuleChannels = (ruleId: string, channelIds: string[]) =>
  apiFetch<AlertRule>(`/api/alerts/rules/${ruleId}/channels`, {
    method: 'PUT',
    body: JSON.stringify({ channel_ids: channelIds }),
  });

// ── Alert history ────────────────────────────────────────────────

export interface AlertHistoryParams {
  rule_id?: string;
  severity?: string;
  acknowledged?: boolean;
  start?: string;
  end?: string;
  limit?: number;
  offset?: number;
}

export const fetchAlertHistory = (params?: AlertHistoryParams, signal?: AbortSignal) =>
  apiFetch<AlertHistory[]>(`/api/alerts/history${buildQueryString({
    rule_id: params?.rule_id,
    severity: params?.severity,
    acknowledged: params?.acknowledged,
    start: params?.start,
    end: params?.end,
    limit: params?.limit,
    offset: params?.offset,
  })}`, { signal });

export const acknowledgeAlert = (historyId: string) =>
  apiFetch<AlertHistory>(`/api/alerts/history/${historyId}/acknowledge`, { method: 'POST' });

// ── Notification channels ────────────────────────────────────────

export interface ChannelListParams {
  plugin_id?: string;
  is_active?: boolean;
}

export const fetchChannels = (params?: ChannelListParams, signal?: AbortSignal) =>
  apiFetch<NotificationChannel[]>(`/api/alerts/channels${buildQueryString({
    plugin_id: params?.plugin_id,
    is_active: params?.is_active,
  })}`, { signal });

export const fetchChannel = (id: string, signal?: AbortSignal) =>
  apiFetch<NotificationChannel>(`/api/alerts/channels/${id}`, { signal });

export const createChannel = (data: NotificationChannelCreate) =>
  apiFetch<NotificationChannel>('/api/alerts/channels', {
    method: 'POST',
    body: JSON.stringify(data),
  });

export const updateChannel = (id: string, data: NotificationChannelUpdate) =>
  apiFetch<NotificationChannel>(`/api/alerts/channels/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  });

export const deleteChannel = (id: string) =>
  apiFetch<void>(`/api/alerts/channels/${id}`, { method: 'DELETE' });
