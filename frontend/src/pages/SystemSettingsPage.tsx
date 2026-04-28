import { useMemo } from 'react';
import { Alert, Center, Loader, Stack, Tabs, Text, Title } from '@mantine/core';
import { notifications } from '@mantine/notifications';
import {
  IconAlertCircle,
  IconBell,
  IconDatabase,
  IconDeviceDesktop,
  IconLayoutDashboard,
} from '@tabler/icons-react';
import {
  useResetSystemSetting,
  useSystemSettings,
  useUpdateSystemSettings,
} from '@/hooks/systemSettings';
import { SettingsTabForm } from '@/components/settings/SettingsTabForm';
import type { SystemSetting, SystemSettingGroup, SystemSettingValue } from '@/types';

const TAB_DEFS: Array<{
  group: SystemSettingGroup;
  label: string;
  Icon: typeof IconDatabase;
}> = [
  { group: 'storage', label: 'Telemetry storage', Icon: IconDatabase },
  { group: 'alerts', label: 'Alerts', Icon: IconBell },
  { group: 'devices', label: 'Devices', Icon: IconDeviceDesktop },
  { group: 'ui', label: 'UI', Icon: IconLayoutDashboard },
];

export function SystemSettingsPage() {
  const { data, isLoading, error } = useSystemSettings();
  const updateMutation = useUpdateSystemSettings();
  const resetMutation = useResetSystemSetting();

  const grouped = useMemo(() => {
    const out: Record<SystemSettingGroup, SystemSetting[]> = {
      storage: [],
      alerts: [],
      devices: [],
      ui: [],
    };
    if (data) {
      for (const setting of data) out[setting.group].push(setting);
    }
    return out;
  }, [data]);

  // Used as a remount key — when any value changes (after save / reset / poll)
  // the per-tab forms remount, naturally clearing their drafts without an effect.
  const baselineKey = useMemo(
    () => (data ?? []).map((s) => `${s.key}=${String(s.value)}`).join('|'),
    [data],
  );

  const handleSave = (changed: Record<string, SystemSettingValue>) => {
    updateMutation.mutate(changed, {
      onSuccess: (resp) => {
        notifications.show({
          color: 'green',
          title: 'Settings saved',
          message: `Updated ${resp.updated.length} setting${resp.updated.length === 1 ? '' : 's'}.`,
        });
        if (resp.requires_restart_keys.length > 0) {
          const services = Array.from(
            new Set(
              resp.updated
                .filter((s) => resp.requires_restart_keys.includes(s.key))
                .flatMap((s) => s.affects_services),
            ),
          );
          notifications.show({
            color: 'yellow',
            title: 'Restart required',
            autoClose: 8000,
            message:
              services.length > 0
                ? `Changes to ${resp.requires_restart_keys.join(', ')} require restarting: ${services.join(', ')}.`
                : `Changes to ${resp.requires_restart_keys.join(', ')} require a service restart.`,
          });
        }
      },
    });
  };

  const handleReset = (key: string) => {
    if (!confirm(`Reset "${key}" to its default value?`)) return;
    resetMutation.mutate(key, {
      onSuccess: () =>
        notifications.show({
          color: 'gray',
          title: 'Reset to default',
          message: key,
        }),
    });
  };

  if (isLoading) {
    return (
      <Center h="50vh">
        <Loader />
      </Center>
    );
  }

  if (error) {
    return (
      <Alert color="red" icon={<IconAlertCircle size={16} />} title="Failed to load settings">
        {error instanceof Error ? error.message : String(error)}
      </Alert>
    );
  }

  return (
    <Stack>
      <Stack gap={4}>
        <Title order={2}>System settings</Title>
        <Text size="sm" c="dimmed">
          Defaults come from the deployed configuration. Overriding a value here
          stores it in the database; resetting removes the override and reverts
          to the default.
        </Text>
      </Stack>

      <Tabs defaultValue="storage" keepMounted={false}>
        <Tabs.List>
          {TAB_DEFS.map(({ group, label, Icon }) => (
            <Tabs.Tab key={group} value={group} leftSection={<Icon size={16} />}>
              {label}
            </Tabs.Tab>
          ))}
        </Tabs.List>

        {TAB_DEFS.map(({ group }) => (
          <Tabs.Panel key={group} value={group} pt="md">
            <SettingsTabForm
              key={`${group}:${baselineKey}`}
              settings={grouped[group]}
              isPending={updateMutation.isPending || resetMutation.isPending}
              onSave={handleSave}
              onReset={handleReset}
            />
          </Tabs.Panel>
        ))}
      </Tabs>
    </Stack>
  );
}
