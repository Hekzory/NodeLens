import { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Group, Select, Button, Text, Center, Stack, Loader, Modal, SegmentedControl,
} from '@mantine/core';
import { IconPlus, IconEdit, IconTrash, IconLayoutGrid, IconRefresh, IconClock } from '@tabler/icons-react';
import { useQueryClient } from '@tanstack/react-query';
import { useDashboards, useDashboard, useCreateDashboard, useUpdateDashboard, useDeleteDashboard } from '@/hooks/dashboards';
import { WidgetGrid } from '@/components/dashboard/WidgetGrid';
import { AddWidgetModal } from '@/components/dashboard/AddWidgetModal';
import { DashboardSettingsModal } from '@/components/dashboard/DashboardSettingsModal';
import { TimeRangeProvider, TIME_PRESETS, useTimeRange } from '@/context/TimeRange';
import type { DashboardCreate } from '@/types';

function TimeRangeSelector() {
  const { preset, setPreset, interval, setInterval, availableIntervals } = useTimeRange();
  return (
    <Group gap="xs">
      <Group gap={4}>
        <IconClock size={14} style={{ opacity: 0.5 }} />
        <SegmentedControl
          size="xs"
          value={preset}
          onChange={setPreset}
          data={TIME_PRESETS.map((p) => ({ label: p.label, value: p.value }))}
        />
      </Group>
      {availableIntervals.length > 1 && (
        <Select
          size="xs"
          value={interval}
          onChange={(v) => setInterval(v ?? '')}
          data={availableIntervals.map((iv) => ({ label: iv.label, value: iv.value }))}
          w={80}
          placeholder="Interval"
          allowDeselect={false}
        />
      )}
    </Group>
  );
}

export function DashboardPage() {
  const { id: paramId } = useParams<{ id?: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { data: dashboards, isLoading: listLoading } = useDashboards();

  const activeDashboardId = paramId ?? dashboards?.find((d) => d.is_default)?.id ?? dashboards?.[0]?.id ?? '';

  const { data: dashboard, isLoading: dashLoading } = useDashboard(activeDashboardId);
  const { mutate: createDashboard, isPending: creating } = useCreateDashboard();
  const { mutate: updateDashboard, isPending: updating } = useUpdateDashboard();
  const { mutate: deleteDashboard } = useDeleteDashboard();

  const [editMode, setEditMode] = useState(false);
  const [addWidgetOpen, setAddWidgetOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [editingDashboard, setEditingDashboard] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState(false);

  const handleCreate = (data: DashboardCreate) => {
    createDashboard(data, {
      onSuccess: (d) => {
        setSettingsOpen(false);
        navigate(`/dashboards/${d.id}`);
      },
    });
  };

  const handleUpdate = (data: DashboardCreate) => {
    updateDashboard({ id: activeDashboardId, data }, { onSuccess: () => setSettingsOpen(false) });
  };

  const handleDelete = () => {
    deleteDashboard(activeDashboardId, { onSuccess: () => navigate('/') });
  };

  if (listLoading) return <Center h="60vh"><Loader /></Center>;

  if (!dashboards?.length) {
    return (
      <Center h="60vh">
        <Stack align="center">
          <IconLayoutGrid size={48} opacity={0.3} />
          <Text c="dimmed">No dashboards yet.</Text>
          <Button onClick={() => { setEditingDashboard(false); setSettingsOpen(true); }}>
            Create Dashboard
          </Button>
          <DashboardSettingsModal
            opened={settingsOpen}
            onClose={() => setSettingsOpen(false)}
            onSubmit={handleCreate}
            isPending={creating}
          />
        </Stack>
      </Center>
    );
  }

  return (
    <TimeRangeProvider>
      <Group mb="md" justify="space-between">
        <Group>
          <Select
            value={activeDashboardId}
            onChange={(v) => v && navigate(v === dashboards?.[0]?.id ? '/' : `/dashboards/${v}`)}
            data={(dashboards ?? []).map((d) => ({ value: d.id, label: d.name }))}
            w={200}
          />
          <TimeRangeSelector />
        </Group>
        <Group>
          <Button
            size="xs"
            variant="default"
            leftSection={<IconRefresh size={14} />}
            onClick={() => {
              queryClient.invalidateQueries({ queryKey: ['dashboards', activeDashboardId] });
              queryClient.invalidateQueries({ queryKey: ['telemetry'] });
            }}
          >
            Refresh
          </Button>
          <Button
            size="xs"
            variant={editMode ? 'filled' : 'default'}
            leftSection={<IconEdit size={14} />}
            onClick={() => setEditMode((e) => !e)}
          >
            {editMode ? 'Done' : 'Edit Layout'}
          </Button>
          {editMode && (
            <>
              <Button
                size="xs"
                variant="default"
                leftSection={<IconPlus size={14} />}
                onClick={() => { setEditingDashboard(false); setSettingsOpen(true); }}
              >
                New
              </Button>
              <Button size="xs" leftSection={<IconPlus size={14} />} onClick={() => setAddWidgetOpen(true)}>
                Add Widget
              </Button>
              <Button
                size="xs"
                variant="default"
                leftSection={<IconEdit size={14} />}
                onClick={() => { setEditingDashboard(true); setSettingsOpen(true); }}
              >
                Settings
              </Button>
              <Button
                size="xs"
                color="red"
                variant="subtle"
                leftSection={<IconTrash size={14} />}
                onClick={() => setDeleteConfirm(true)}
              >
                Delete
              </Button>
            </>
          )}
        </Group>
      </Group>

      {dashLoading ? (
        <Center h="40vh"><Loader /></Center>
      ) : dashboard?.widgets.length === 0 ? (
        <Center h="40vh">
          <Stack align="center">
            <Text c="dimmed">No widgets yet.</Text>
            <Button onClick={() => { setEditMode(true); setAddWidgetOpen(true); }}>
              Add Widget
            </Button>
          </Stack>
        </Center>
      ) : (
        <WidgetGrid
          widgets={dashboard?.widgets ?? []}
          dashboardId={activeDashboardId}
          editMode={editMode}
        />
      )}

      <AddWidgetModal
        opened={addWidgetOpen}
        onClose={() => setAddWidgetOpen(false)}
        dashboardId={activeDashboardId}
      />

      <DashboardSettingsModal
        opened={settingsOpen}
        onClose={() => setSettingsOpen(false)}
        onSubmit={editingDashboard ? handleUpdate : handleCreate}
        initial={editingDashboard ? dashboard as typeof dashboard & { id: string; widget_count: number } : undefined}
        isPending={creating || updating}
      />

      <Modal opened={deleteConfirm} onClose={() => setDeleteConfirm(false)} title="Delete Dashboard?" size="sm">
        <Text mb="md">This will permanently delete the dashboard and all its widgets.</Text>
        <Group justify="flex-end">
          <Button variant="default" onClick={() => setDeleteConfirm(false)}>Cancel</Button>
          <Button color="red" onClick={handleDelete}>Delete</Button>
        </Group>
      </Modal>
    </TimeRangeProvider>
  );
}
