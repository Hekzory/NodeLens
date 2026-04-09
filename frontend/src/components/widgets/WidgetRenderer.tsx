import { Component, type ReactNode } from 'react';
import { Paper, ActionIcon, Group, Text, Center, Stack } from '@mantine/core';
import { IconX, IconPencil, IconAlertTriangle } from '@tabler/icons-react';
import { ChartWidget } from './ChartWidget';
import { GaugeWidget } from './GaugeWidget';
import { StatCardWidget } from './StatCardWidget';
import { StatusWidget } from './StatusWidget';
import { useDeleteWidget } from '@/hooks/dashboards';
import type { Widget } from '@/types';

class WidgetErrorBoundary extends Component<
  { children: ReactNode },
  { hasError: boolean }
> {
  state = { hasError: false };
  static getDerivedStateFromError() { return { hasError: true }; }

  render() {
    if (this.state.hasError) {
      return (
        <Center h="100%">
          <Stack align="center" gap={4}>
            <IconAlertTriangle size={20} color="var(--mantine-color-yellow-6)" />
            <Text size="xs" c="dimmed">Widget failed to render</Text>
          </Stack>
        </Center>
      );
    }
    return this.props.children;
  }
}

const WIDGET_MAP: Record<string, (props: { widget: Widget }) => ReactNode> = {
  chart: ChartWidget,
  gauge: GaugeWidget,
  stat_card: StatCardWidget,
  status: StatusWidget,
};

interface Props {
  widget: Widget;
  dashboardId: string;
  editMode?: boolean;
  onEdit?: (widget: Widget) => void;
}

export function WidgetRenderer({ widget, dashboardId, editMode, onEdit }: Props) {
  const { mutate: deleteWidget } = useDeleteWidget(dashboardId);
  const WidgetComponent = WIDGET_MAP[widget.widget_type];

  return (
    <Paper h="100%" p="md" withBorder style={{ position: 'relative', overflow: 'hidden' }}>
      <Text size="xs" c="dimmed" mb={4} pr={editMode ? 44 : 0} truncate>
        {widget.title}
      </Text>
      {editMode && (
        <Group gap={2} style={{ position: 'absolute', top: 8, right: 8 }}>
          <ActionIcon
            size="xs"
            variant="subtle"
            color="gray"
            onClick={() => onEdit?.(widget)}
          >
            <IconPencil size={12} />
          </ActionIcon>
          <ActionIcon
            size="xs"
            variant="subtle"
            color="red"
            onClick={() => deleteWidget(widget.id)}
          >
            <IconX size={12} />
          </ActionIcon>
        </Group>
      )}
      <div style={{ height: 'calc(100% - 24px)' }}>
        <WidgetErrorBoundary>
          {WidgetComponent
            ? <WidgetComponent widget={widget} />
            : <Center h="100%"><Text size="sm" c="dimmed">Unknown widget type</Text></Center>
          }
        </WidgetErrorBoundary>
      </div>
    </Paper>
  );
}
