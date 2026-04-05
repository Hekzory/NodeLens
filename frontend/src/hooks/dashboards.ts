import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  fetchDashboards,
  fetchDashboard,
  createDashboard,
  updateDashboard,
  deleteDashboard,
  createWidget,
  updateWidget,
  deleteWidget,
} from '@/api/dashboards';
import type { DashboardCreate, DashboardUpdate, WidgetCreate, WidgetUpdate } from '@/types';

export const useDashboards = () =>
  useQuery({ queryKey: ['dashboards'], queryFn: fetchDashboards });

export const useDashboard = (id: string) =>
  useQuery({
    queryKey: ['dashboards', id],
    queryFn: () => fetchDashboard(id),
    enabled: !!id,
    refetchInterval: 10_000,
  });

export const useCreateDashboard = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: DashboardCreate) => createDashboard(data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['dashboards'] }),
  });
};

export const useUpdateDashboard = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: DashboardUpdate }) => updateDashboard(id, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['dashboards'] }),
  });
};

export const useDeleteDashboard = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => deleteDashboard(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['dashboards'] }),
  });
};

export const useCreateWidget = (dashboardId: string) => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: WidgetCreate) => createWidget(dashboardId, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['dashboards', dashboardId] }),
  });
};

export const useUpdateWidget = (dashboardId: string) => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ widgetId, data }: { widgetId: string; data: WidgetUpdate }) =>
      updateWidget(dashboardId, widgetId, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['dashboards', dashboardId] }),
  });
};

export const useDeleteWidget = (dashboardId: string) => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (widgetId: string) => deleteWidget(dashboardId, widgetId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['dashboards', dashboardId] }),
  });
};
