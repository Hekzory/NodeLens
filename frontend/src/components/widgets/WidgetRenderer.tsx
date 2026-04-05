import { Paper, ActionIcon, Text } from '@mantine/core';
import { IconX } from '@tabler/icons-react';
import { ChartWidget } from './ChartWidget';
import { GaugeWidget } from './GaugeWidget';
import { StatCardWidget } from './StatCardWidget';
import { StatusWidget } from './StatusWidget';
import { useDeleteWidget } from '@/hooks/dashboards';
import type { Widget } from '@/types';

interface Props {
  widget: Widget;
  dashboardId: string;
  editMode?: boolean;
}

export function WidgetRenderer({ widget, dashboardId, editMode }: Props) {
  const { mutate: deleteWidget } = useDeleteWidget(dashboardId);

  return (
    <Paper h="100%" p="md" withBorder style={{ position: 'relative', overflow: 'hidden' }}>
      <Text size="xs" c="dimmed" mb={4} pr={editMode ? 24 : 0}>
        {widget.title}
      </Text>
      {editMode && (
        <ActionIcon
          size="xs"
          variant="subtle"
          color="red"
          style={{ position: 'absolute', top: 8, right: 8 }}
          onClick={() => deleteWidget(widget.id)}
        >
          <IconX size={12} />
        </ActionIcon>
      )}
      <div style={{ height: 'calc(100% - 24px)' }}>
        {widget.widget_type === 'chart' && <ChartWidget widget={widget} />}
        {widget.widget_type === 'gauge' && <GaugeWidget widget={widget} />}
        {widget.widget_type === 'stat_card' && <StatCardWidget widget={widget} />}
        {widget.widget_type === 'status' && <StatusWidget widget={widget} />}
      </div>
    </Paper>
  );
}
