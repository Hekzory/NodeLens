import { apiFetch } from './client';
import type {
  Dashboard,
  DashboardDetail,
  DashboardCreate,
  DashboardUpdate,
  Widget,
  WidgetCreate,
  WidgetUpdate,
} from '@/types';

export const fetchDashboards = () => apiFetch<Dashboard[]>('/api/dashboards');
export const fetchDashboard = (id: string) => apiFetch<DashboardDetail>(`/api/dashboards/${id}`);
export const createDashboard = (data: DashboardCreate) =>
  apiFetch<Dashboard>('/api/dashboards', { method: 'POST', body: JSON.stringify(data) });
export const updateDashboard = (id: string, data: DashboardUpdate) =>
  apiFetch<Dashboard>(`/api/dashboards/${id}`, { method: 'PATCH', body: JSON.stringify(data) });
export const deleteDashboard = (id: string) =>
  apiFetch<void>(`/api/dashboards/${id}`, { method: 'DELETE' });

export const createWidget = (dashboardId: string, data: WidgetCreate) =>
  apiFetch<Widget>(`/api/dashboards/${dashboardId}/widgets`, {
    method: 'POST',
    body: JSON.stringify(data),
  });
export const updateWidget = (dashboardId: string, widgetId: string, data: WidgetUpdate) =>
  apiFetch<Widget>(`/api/dashboards/${dashboardId}/widgets/${widgetId}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  });
export const deleteWidget = (dashboardId: string, widgetId: string) =>
  apiFetch<void>(`/api/dashboards/${dashboardId}/widgets/${widgetId}`, { method: 'DELETE' });
