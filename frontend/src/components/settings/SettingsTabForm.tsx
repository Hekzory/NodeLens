import { useState } from 'react';
import {
  Badge,
  Button,
  Group,
  NumberInput,
  Stack,
  Switch,
  Text,
  TextInput,
  Tooltip,
} from '@mantine/core';
import { IconRotateClockwise } from '@tabler/icons-react';
import type { SystemSetting, SystemSettingValue } from '@/types';

type Props = {
  settings: SystemSetting[];
  isPending: boolean;
  onSave: (changed: Record<string, SystemSettingValue>) => void;
  onReset: (key: string) => void;
};

const inputForSetting = (
  setting: SystemSetting,
  draftValue: SystemSettingValue | undefined,
  onChange: (next: SystemSettingValue) => void,
) => {
  const current = draftValue ?? setting.value;

  if (setting.value_type === 'bool') {
    return (
      <Switch
        checked={Boolean(current)}
        onChange={(e) => onChange(e.currentTarget.checked)}
      />
    );
  }

  if (setting.value_type === 'int' || setting.value_type === 'float') {
    return (
      <NumberInput
        value={typeof current === 'number' ? current : Number(current)}
        onChange={(v) => onChange(typeof v === 'number' ? v : Number(v))}
        min={setting.min ?? undefined}
        max={setting.max ?? undefined}
        step={setting.value_type === 'int' ? 1 : undefined}
        allowDecimal={setting.value_type === 'float'}
        suffix={setting.unit ? ` ${setting.unit}` : undefined}
        w={220}
      />
    );
  }

  return (
    <TextInput
      value={String(current ?? '')}
      onChange={(e) => onChange(e.currentTarget.value)}
      w={320}
    />
  );
};

export function SettingsTabForm({ settings, isPending, onSave, onReset }: Props) {
  // Draft maps from key → value; only changed keys are present.
  // The parent remounts this component (via `key`) whenever the underlying
  // settings refetch, so the draft naturally resets without an effect.
  const [draft, setDraft] = useState<Record<string, SystemSettingValue>>({});

  const handleChange = (key: string, value: SystemSettingValue) => {
    setDraft((d) => ({ ...d, [key]: value }));
  };

  const dirty = Object.keys(draft).length > 0;

  const handleSave = () => {
    if (!dirty) return;
    // Strip values that match the baseline so we only PATCH actual changes.
    const changed: Record<string, SystemSettingValue> = {};
    for (const [key, value] of Object.entries(draft)) {
      const baseline = settings.find((s) => s.key === key)?.value;
      if (value !== baseline) changed[key] = value;
    }
    if (Object.keys(changed).length === 0) {
      setDraft({});
      return;
    }
    onSave(changed);
  };

  return (
    <Stack gap="md">
      {settings.length === 0 && (
        <Text c="dimmed">No settings in this group.</Text>
      )}
      {settings.map((setting) => (
        <Group key={setting.key} align="flex-start" wrap="nowrap" gap="md">
          <Stack gap={2} style={{ flex: 1 }}>
            <Group gap={6}>
              <Text fw={500}>{setting.label}</Text>
              {setting.requires_restart && (
                <Tooltip
                  label={
                    setting.affects_services.length > 0
                      ? `Restart required: ${setting.affects_services.join(', ')}`
                      : 'Restart required for changes to take effect'
                  }
                >
                  <Badge size="xs" color="yellow" variant="light">
                    restart required
                  </Badge>
                </Tooltip>
              )}
              {!setting.is_default && (
                <Badge size="xs" color="blue" variant="light">
                  overridden
                </Badge>
              )}
            </Group>
            <Text size="xs" c="dimmed">
              {setting.help}
            </Text>
            <Text size="xs" c="dimmed">
              Default: <span className="nl-mono">{String(setting.default)}</span>
              {setting.unit ? ` ${setting.unit}` : ''}
            </Text>
          </Stack>
          <Group gap="xs" wrap="nowrap">
            {inputForSetting(setting, draft[setting.key], (v) =>
              handleChange(setting.key, v),
            )}
            <Tooltip label="Reset to default" disabled={setting.is_default}>
              <Button
                variant="subtle"
                size="compact-sm"
                color="gray"
                disabled={setting.is_default}
                onClick={() => onReset(setting.key)}
                aria-label={`Reset ${setting.label}`}
              >
                <IconRotateClockwise size={16} />
              </Button>
            </Tooltip>
          </Group>
        </Group>
      ))}

      <Group justify="flex-end" mt="sm">
        <Button variant="default" disabled={!dirty || isPending} onClick={() => setDraft({})}>
          Discard
        </Button>
        <Button loading={isPending} disabled={!dirty} onClick={handleSave}>
          Save
        </Button>
      </Group>
    </Stack>
  );
}
