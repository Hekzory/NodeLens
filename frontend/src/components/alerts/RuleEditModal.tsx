import {
  Modal,
  TextInput,
  Textarea,
  NumberInput,
  Select,
  MultiSelect,
  SegmentedControl,
  Checkbox,
  Button,
  Stack,
  Group,
  Text,
} from '@mantine/core';
import { useForm } from '@mantine/form';
import { useEffect, useState } from 'react';
import { useDevices, useDeviceSensors } from '@/hooks/devices';
import { useChannels } from '@/hooks/alerts';
import type {
  AlertAggregation,
  AlertCondition,
  AlertRule,
  AlertRuleCreate,
  AlertRuleType,
  AlertSeverity,
} from '@/types';

interface Props {
  opened: boolean;
  onClose: () => void;
  onSubmit: (data: AlertRuleCreate, channelIds: string[]) => void;
  initial?: AlertRule;
  isPending?: boolean;
}

interface FormValues {
  name: string;
  description: string;
  sensor_id: string;
  rule_type: AlertRuleType;
  condition: AlertCondition;
  threshold: number | '';
  aggregation: AlertAggregation | '';
  duration_seconds: number;
  cooldown_seconds: number;
  severity: AlertSeverity;
  is_active: boolean;
  channel_ids: string[];
}

const EMPTY: FormValues = {
  name: '',
  description: '',
  sensor_id: '',
  rule_type: 'instant',
  condition: 'gt',
  threshold: '',
  aggregation: '',
  duration_seconds: 60,
  cooldown_seconds: 300,
  severity: 'warning',
  is_active: true,
  channel_ids: [],
};

const CONDITIONS = [
  { value: 'gt', label: '> (greater than)' },
  { value: 'gte', label: '≥ (greater or equal)' },
  { value: 'lt', label: '< (less than)' },
  { value: 'lte', label: '≤ (less or equal)' },
  { value: 'eq', label: '= (equal)' },
  { value: 'neq', label: '≠ (not equal)' },
  { value: 'no_data', label: 'no data (not yet evaluated)' },
];

const AGGREGATIONS = [
  { value: 'avg', label: 'average' },
  { value: 'min', label: 'minimum' },
  { value: 'max', label: 'maximum' },
  { value: 'sum', label: 'sum' },
  { value: 'count', label: 'count' },
];

const SEVERITIES = [
  { value: 'info', label: 'info' },
  { value: 'warning', label: 'warning' },
  { value: 'critical', label: 'critical' },
];

export function RuleEditModal({ opened, onClose, onSubmit, initial, isPending }: Props) {
  const [deviceId, setDeviceId] = useState<string | null>(null);
  const { data: devices } = useDevices();
  const { data: sensors } = useDeviceSensors(deviceId ?? '');
  const { data: channels } = useChannels();

  const form = useForm<FormValues>({ initialValues: EMPTY });

  useEffect(() => {
    if (!opened) return;
    if (initial) {
      form.setValues({
        name: initial.name,
        description: initial.description ?? '',
        sensor_id: initial.sensor_id,
        rule_type: initial.rule_type,
        condition: initial.condition,
        threshold: initial.threshold ?? '',
        aggregation: initial.aggregation ?? '',
        duration_seconds: initial.duration_seconds,
        cooldown_seconds: initial.cooldown_seconds,
        severity: initial.severity,
        is_active: initial.is_active,
        channel_ids: initial.channel_ids ?? [],
      });
    } else {
      form.reset();
      setDeviceId(null);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initial, opened]);

  const handleSubmit = form.onSubmit((values) => {
    const data: AlertRuleCreate = {
      name: values.name,
      description: values.description || null,
      sensor_id: values.sensor_id,
      rule_type: values.rule_type,
      condition: values.condition,
      threshold:
        values.condition === 'no_data'
          ? null
          : values.threshold === ''
            ? null
            : Number(values.threshold),
      aggregation: values.rule_type === 'aggregated' ? (values.aggregation || null) : null,
      duration_seconds: values.rule_type === 'aggregated' ? values.duration_seconds : 0,
      cooldown_seconds: values.cooldown_seconds,
      severity: values.severity,
      is_active: values.is_active,
    };
    onSubmit(data, values.channel_ids);
  });

  const isEditing = !!initial;
  const channelOptions = (channels ?? []).map((c) => ({
    value: c.id,
    label: `${c.name}${c.plugin_module_name ? ` (${c.plugin_module_name})` : ''}`,
  }));

  return (
    <Modal
      opened={opened}
      onClose={onClose}
      title={isEditing ? 'Edit Alert Rule' : 'New Alert Rule'}
      size="md"
    >
      <form onSubmit={handleSubmit}>
        <Stack>
          <TextInput label="Name" required {...form.getInputProps('name')} />
          <Textarea label="Description" autosize {...form.getInputProps('description')} />

          {!isEditing ? (
            <>
              <Select
                label="Device"
                placeholder={devices?.length ? 'Pick a device' : 'No devices available'}
                data={(devices ?? []).map((d) => ({ value: d.id, label: d.name }))}
                value={deviceId}
                onChange={(val) => {
                  setDeviceId(val);
                  form.setFieldValue('sensor_id', '');
                }}
                disabled={!devices?.length}
                searchable
              />
              <Select
                label="Sensor"
                placeholder={deviceId ? 'Pick a sensor' : 'Select a device first'}
                required
                data={(sensors ?? []).map((s) => ({
                  value: s.id,
                  label: `${s.name}${s.unit ? ` (${s.unit})` : ''}`,
                }))}
                value={form.values.sensor_id || null}
                onChange={(val) => form.setFieldValue('sensor_id', val ?? '')}
                disabled={!deviceId}
                searchable
              />
            </>
          ) : (
            <div>
              <Text size="sm" fw={500} mb={4}>Sensor</Text>
              <Text size="xs" c="dimmed" className="nl-mono">{form.values.sensor_id}</Text>
              <Text size="xs" c="dimmed">Sensor is locked while editing — delete and recreate to switch.</Text>
            </div>
          )}

          <div>
            <Text size="sm" fw={500} mb={4}>Rule type</Text>
            <SegmentedControl
              fullWidth
              data={[
                { label: 'Instant', value: 'instant' },
                { label: 'Aggregated', value: 'aggregated' },
              ]}
              value={form.values.rule_type}
              onChange={(v) => form.setFieldValue('rule_type', v as AlertRuleType)}
            />
          </div>

          <Select
            label="Condition"
            data={CONDITIONS}
            value={form.values.condition}
            onChange={(v) => form.setFieldValue('condition', (v ?? 'gt') as AlertCondition)}
          />

          {form.values.condition !== 'no_data' && (
            <NumberInput
              label="Threshold"
              required
              decimalScale={4}
              value={form.values.threshold}
              onChange={(v) => form.setFieldValue('threshold', v === '' ? '' : Number(v))}
            />
          )}

          {form.values.rule_type === 'aggregated' && (
            <>
              <Select
                label="Aggregation"
                required
                data={AGGREGATIONS}
                value={form.values.aggregation || null}
                onChange={(v) =>
                  form.setFieldValue('aggregation', (v ?? '') as AlertAggregation | '')
                }
              />
              <NumberInput
                label="Window (seconds)"
                required
                min={1}
                {...form.getInputProps('duration_seconds')}
              />
            </>
          )}

          <NumberInput
            label="Cooldown (seconds)"
            min={0}
            {...form.getInputProps('cooldown_seconds')}
          />
          <Select
            label="Severity"
            data={SEVERITIES}
            value={form.values.severity}
            onChange={(v) => form.setFieldValue('severity', (v ?? 'warning') as AlertSeverity)}
          />
          <MultiSelect
            label="Channels"
            placeholder={channelOptions.length ? 'Pick channels' : 'No channels configured'}
            data={channelOptions}
            value={form.values.channel_ids}
            onChange={(v) => form.setFieldValue('channel_ids', v)}
            searchable
          />
          <Checkbox
            label="Active"
            {...form.getInputProps('is_active', { type: 'checkbox' })}
          />

          <Group justify="flex-end">
            <Button variant="default" onClick={onClose}>Cancel</Button>
            <Button type="submit" loading={isPending}>{isEditing ? 'Save' : 'Create'}</Button>
          </Group>
        </Stack>
      </form>
    </Modal>
  );
}
