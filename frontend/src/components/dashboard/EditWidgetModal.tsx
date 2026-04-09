import { Modal, TextInput, NumberInput, Button, Stack, Group } from '@mantine/core';
import { useForm } from '@mantine/form';
import { useEffect } from 'react';
import { useUpdateWidget } from '@/hooks/dashboards';
import type { Widget } from '@/types';

interface Props {
  opened: boolean;
  onClose: () => void;
  dashboardId: string;
  widget: Widget | null;
}

interface FormValues {
  title: string;
  unit: string;
  min: number | '';
  max: number | '';
  warning: number | '';
  critical: number | '';
}

const UNIT_TYPES = ['gauge', 'stat_card'] as const;

export function EditWidgetModal({ opened, onClose, dashboardId, widget }: Props) {
  const { mutate: updateWidget, isPending } = useUpdateWidget(dashboardId);

  const form = useForm<FormValues>({
    initialValues: { title: '', unit: '', min: 0, max: 100, warning: '', critical: '' },
  });

  useEffect(() => {
    if (widget && opened) {
      form.setValues({
        title: widget.title,
        unit: (widget.config.unit as string) ?? '',
        min: (widget.config.min as number) ?? 0,
        max: (widget.config.max as number) ?? 100,
        warning: (widget.config.warning as number) ?? '',
        critical: (widget.config.critical as number) ?? '',
      });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [widget?.id, opened]);

  if (!widget) return null;

  const isGauge = widget.widget_type === 'gauge';
  const hasUnit = (UNIT_TYPES as readonly string[]).includes(widget.widget_type);

  const handleSubmit = form.onSubmit((values) => {
    const config: Record<string, unknown> = { ...widget.config };

    if (hasUnit) {
      config.unit = values.unit || undefined;
    }

    if (isGauge) {
      config.min = values.min === '' ? 0 : values.min;
      config.max = values.max === '' ? 100 : values.max;
      config.warning = values.warning === '' ? undefined : values.warning;
      config.critical = values.critical === '' ? undefined : values.critical;
    }

    updateWidget(
      { widgetId: widget.id, data: { title: values.title, config } },
      { onSuccess: () => onClose() },
    );
  });

  return (
    <Modal opened={opened} onClose={onClose} title="Edit Widget" size="sm">
      <form onSubmit={handleSubmit}>
        <Stack>
          <TextInput label="Title" {...form.getInputProps('title')} />

          {hasUnit && (
            <TextInput
              label="Unit"
              placeholder="e.g. °C, %, hPa"
              {...form.getInputProps('unit')}
            />
          )}

          {isGauge && (
            <>
              <Group grow>
                <NumberInput label="Min" {...form.getInputProps('min')} />
                <NumberInput label="Max" {...form.getInputProps('max')} />
              </Group>
              <Group grow>
                <NumberInput
                  label="Warning %"
                  placeholder="Off"
                  min={0}
                  max={100}
                  {...form.getInputProps('warning')}
                />
                <NumberInput
                  label="Critical %"
                  placeholder="Off"
                  min={0}
                  max={100}
                  {...form.getInputProps('critical')}
                />
              </Group>
            </>
          )}

          <Group justify="flex-end">
            <Button variant="default" onClick={onClose}>Cancel</Button>
            <Button type="submit" loading={isPending}>Save</Button>
          </Group>
        </Stack>
      </form>
    </Modal>
  );
}
