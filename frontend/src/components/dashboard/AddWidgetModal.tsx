import { Modal, SegmentedControl, Select, TextInput, Button, Stack, Group, Text } from '@mantine/core';
import { useForm } from '@mantine/form';
import { useState } from 'react';
import { useDevices } from '@/hooks/devices';
import { useDeviceSensors } from '@/hooks/devices';
import { useCreateWidget } from '@/hooks/dashboards';
import { DEFAULT_WIDGET_SIZES, type WidgetType } from '@/types';

interface Props {
  opened: boolean;
  onClose: () => void;
  dashboardId: string;
}

const WIDGET_TYPES: { label: string; value: WidgetType }[] = [
  { label: 'Chart', value: 'chart' },
  { label: 'Gauge', value: 'gauge' },
  { label: 'Stat Card', value: 'stat_card' },
  { label: 'Status', value: 'status' },
];

export function AddWidgetModal({ opened, onClose, dashboardId }: Props) {
  const [deviceId, setDeviceId] = useState<string | null>(null);
  const { data: devices } = useDevices();
  const { data: sensors } = useDeviceSensors(deviceId ?? '');
  const { mutate: createWidget, isPending } = useCreateWidget(dashboardId);

  const form = useForm({
    initialValues: { widget_type: 'chart' as WidgetType, sensor_id: '', title: '' },
  });

  const handleDeviceChange = (val: string | null) => {
    setDeviceId(val);
    form.setFieldValue('sensor_id', '');
    form.setFieldValue('title', '');
  };

  const handleSensorChange = (val: string | null) => {
    form.setFieldValue('sensor_id', val ?? '');
    const sensor = sensors?.find((s) => s.id === val);
    if (sensor) form.setFieldValue('title', sensor.name);
  };

  const handleSubmit = form.onSubmit((values) => {
    const size = DEFAULT_WIDGET_SIZES[values.widget_type];
    createWidget(
      {
        widget_type: values.widget_type,
        title: values.title || 'Widget',
        sensor_id: values.sensor_id || undefined,
        config: {},
        layout: { x: 0, y: Infinity, ...size },
      },
      {
        onSuccess: () => {
          form.reset();
          setDeviceId(null);
          onClose();
        },
      }
    );
  });

  return (
    <Modal opened={opened} onClose={onClose} title="Add Widget" size="sm">
      <form onSubmit={handleSubmit}>
        <Stack>
          <div>
            <Text size="sm" fw={500} mb={4}>Widget Type</Text>
            <SegmentedControl
              fullWidth
              data={WIDGET_TYPES}
              value={form.values.widget_type}
              onChange={(v) => form.setFieldValue('widget_type', v as WidgetType)}
            />
          </div>
          <Select
            label="Device"
            placeholder={devices?.length ? 'Pick a device' : 'No devices available'}
            data={(devices ?? []).map((d) => ({ value: d.id, label: d.name }))}
            value={deviceId}
            onChange={handleDeviceChange}
            disabled={!devices?.length}
            searchable
          />
          <Select
            label="Sensor"
            placeholder={deviceId ? 'Pick a sensor' : 'Select device first'}
            data={(sensors ?? []).map((s) => ({ value: s.id, label: `${s.name}${s.unit ? ` (${s.unit})` : ''}` }))}
            value={form.values.sensor_id || null}
            onChange={handleSensorChange}
            disabled={!deviceId}
            searchable
          />
          <TextInput label="Title" placeholder="Widget title" {...form.getInputProps('title')} />
          <Group justify="flex-end">
            <Button variant="default" onClick={onClose}>Cancel</Button>
            <Button type="submit" loading={isPending}>Add Widget</Button>
          </Group>
        </Stack>
      </form>
    </Modal>
  );
}
