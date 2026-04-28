import { useMemo, useState } from 'react';
import {
  Alert,
  Badge,
  Button,
  Center,
  Group,
  Loader,
  NumberInput,
  PasswordInput,
  Stack,
  Switch,
  Tabs,
  Text,
  TextInput,
  Tooltip,
} from '@mantine/core';
import { notifications } from '@mantine/notifications';
import { IconAlertCircle, IconRotateClockwise } from '@tabler/icons-react';
import {
  usePluginConfig,
  useResetPluginConfig,
  useUpdatePluginConfig,
} from '@/hooks/plugins';
import type { PluginConfigField, PluginConfigValue } from '@/types';

type Props = {
  pluginId: string;
};

function inputForField(
  field: PluginConfigField,
  draftValue: PluginConfigValue | undefined,
  onChange: (next: PluginConfigValue) => void,
) {
  if (field.value_type === 'bool') {
    const current = draftValue ?? field.value ?? false;
    return (
      <Switch
        checked={Boolean(current)}
        onChange={(e) => onChange(e.currentTarget.checked)}
      />
    );
  }

  if (field.value_type === 'int' || field.value_type === 'float') {
    const current = draftValue ?? field.value ?? 0;
    return (
      <NumberInput
        value={typeof current === 'number' ? current : Number(current)}
        onChange={(v) => onChange(typeof v === 'number' ? v : Number(v))}
        min={field.min ?? undefined}
        max={field.max ?? undefined}
        step={field.value_type === 'int' ? 1 : undefined}
        allowDecimal={field.value_type === 'float'}
        suffix={field.unit ? ` ${field.unit}` : undefined}
        w={220}
      />
    );
  }

  if (field.value_type === 'secret') {
    // Empty string is the sentinel for "preserve existing". The backend
    // never echoes the real secret — `field.value` is either `null` (unset)
    // or the masked sentinel — so we always start the input empty.
    return (
      <PasswordInput
        value={typeof draftValue === 'string' ? draftValue : ''}
        onChange={(e) => onChange(e.currentTarget.value)}
        placeholder={
          field.is_default ? 'Not set' : 'Leave blank to keep existing'
        }
        w={320}
      />
    );
  }

  // string
  const current = draftValue ?? field.value ?? '';
  return (
    <TextInput
      value={String(current)}
      onChange={(e) => onChange(e.currentTarget.value)}
      w={320}
    />
  );
}

function FieldRow({
  field,
  draft,
  onChange,
  onReset,
  resetDisabled,
}: {
  field: PluginConfigField;
  draft: PluginConfigValue | undefined;
  onChange: (key: string, value: PluginConfigValue) => void;
  onReset: (key: string) => void;
  resetDisabled: boolean;
}) {
  return (
    <Group align="flex-start" wrap="nowrap" gap="md">
      <Stack gap={2} style={{ flex: 1 }}>
        <Group gap={6}>
          <Text fw={500}>{field.label}</Text>
          {field.value_type === 'secret' && !field.is_default && (
            <Badge size="xs" color="blue" variant="light">
              secret set
            </Badge>
          )}
          {field.value_type !== 'secret' && !field.is_default && (
            <Badge size="xs" color="blue" variant="light">
              overridden
            </Badge>
          )}
          {field.requires_restart && (
            <Tooltip label="Restart required for changes to take effect">
              <Badge size="xs" color="yellow" variant="light">
                restart required
              </Badge>
            </Tooltip>
          )}
        </Group>
        {field.help && (
          <Text size="xs" c="dimmed">
            {field.help}
          </Text>
        )}
        {field.value_type !== 'secret' && (
          <Text size="xs" c="dimmed">
            Default:{' '}
            <span className="nl-mono">{String(field.default ?? '')}</span>
            {field.unit ? ` ${field.unit}` : ''}
          </Text>
        )}
        <Text size="xs" c="dimmed" className="nl-mono">
          {field.key}
        </Text>
      </Stack>
      <Group gap="xs" wrap="nowrap">
        {inputForField(field, draft, (v) => onChange(field.key, v))}
        <Tooltip label="Reset to default" disabled={resetDisabled}>
          <Button
            variant="subtle"
            size="compact-sm"
            color="gray"
            disabled={resetDisabled}
            onClick={() => onReset(field.key)}
            aria-label={`Reset ${field.label}`}
          >
            <IconRotateClockwise size={16} />
          </Button>
        </Tooltip>
      </Group>
    </Group>
  );
}

export function PluginConfigForm({ pluginId }: Props) {
  const { data, isLoading, error } = usePluginConfig(pluginId);
  const updateMutation = useUpdatePluginConfig(pluginId);
  const resetMutation = useResetPluginConfig(pluginId);

  // Draft maps from key → value; only changed keys are present.
  const [draft, setDraft] = useState<Record<string, PluginConfigValue>>({});
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

  const groups = useMemo(() => {
    const map = new Map<string, PluginConfigField[]>();
    for (const f of data?.fields ?? []) {
      const arr = map.get(f.group) ?? [];
      arr.push(f);
      map.set(f.group, arr);
    }
    return Array.from(map.entries());
  }, [data]);

  // Remount key — when version bumps after save, the local draft naturally
  // resets without an effect.
  const baselineKey = data?.config_version ?? 0;

  if (isLoading) {
    return (
      <Center py="md">
        <Loader />
      </Center>
    );
  }

  if (error) {
    return (
      <Alert color="red" icon={<IconAlertCircle size={16} />} title="Failed to load configuration">
        {error instanceof Error ? error.message : String(error)}
      </Alert>
    );
  }

  if (!data || data.fields.length === 0) {
    return (
      <Text c="dimmed" size="sm">
        This plugin does not declare any configurable parameters.
      </Text>
    );
  }

  const handleChange = (key: string, value: PluginConfigValue) => {
    setDraft((d) => ({ ...d, [key]: value }));
    setFieldErrors((errs) => {
      if (!(key in errs)) return errs;
      const { [key]: _omit, ...rest } = errs;
      return rest;
    });
  };

  const handleSave = () => {
    if (Object.keys(draft).length === 0) return;
    setFieldErrors({});
    updateMutation.mutate(draft, {
      onSuccess: () => {
        setDraft({});
        notifications.show({
          color: 'blue',
          title: 'Plugin restarting',
          message: 'Configuration saved — the plugin will restart with the new values.',
          autoClose: 6000,
        });
      },
      onError: (err) => {
        // The error message format from apiFetch is "<status> <detail>".
        // We try to recover field_errors from a JSON detail; if the server
        // returned a plain string, we surface it as a top-level alert.
        const msg = err instanceof Error ? err.message : String(err);
        const match = msg.match(/^\d+\s+(.+)$/);
        const body = match ? match[1] : msg;
        try {
          const parsed = JSON.parse(body);
          if (parsed && typeof parsed === 'object' && 'field_errors' in parsed) {
            setFieldErrors(parsed.field_errors as Record<string, string>);
            return;
          }
        } catch {
          /* fall through */
        }
        notifications.show({
          color: 'red',
          title: 'Save failed',
          message: body,
        });
      },
    });
  };

  const handleReset = (key: string) => {
    if (!confirm(`Reset "${key}" to its default?`)) return;
    resetMutation.mutate(key, {
      onSuccess: () =>
        notifications.show({
          color: 'gray',
          title: 'Reset to default',
          message: key,
        }),
    });
  };

  const dirty = Object.keys(draft).length > 0;
  const isPending = updateMutation.isPending || resetMutation.isPending;

  const renderFields = (fields: PluginConfigField[]) => (
    <Stack gap="md">
      {fields.map((f) => (
        <Stack key={`${baselineKey}:${f.key}`} gap={4}>
          <FieldRow
            field={f}
            draft={draft[f.key]}
            onChange={handleChange}
            onReset={handleReset}
            resetDisabled={f.is_default}
          />
          {fieldErrors[f.key] && (
            <Text size="xs" c="red">
              {fieldErrors[f.key]}
            </Text>
          )}
        </Stack>
      ))}
    </Stack>
  );

  return (
    <Stack gap="md">
      {groups.length === 1 ? (
        renderFields(groups[0][1])
      ) : (
        <Tabs defaultValue={groups[0][0]} keepMounted={false}>
          <Tabs.List>
            {groups.map(([name]) => (
              <Tabs.Tab key={name} value={name}>
                {name}
              </Tabs.Tab>
            ))}
          </Tabs.List>
          {groups.map(([name, fields]) => (
            <Tabs.Panel key={name} value={name} pt="md">
              {renderFields(fields)}
            </Tabs.Panel>
          ))}
        </Tabs>
      )}

      <Group justify="flex-end" mt="sm">
        <Button
          variant="default"
          disabled={!dirty || isPending}
          onClick={() => {
            setDraft({});
            setFieldErrors({});
          }}
        >
          Discard
        </Button>
        <Button loading={updateMutation.isPending} disabled={!dirty} onClick={handleSave}>
          Save
        </Button>
      </Group>
    </Stack>
  );
}
