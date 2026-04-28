import { useParams, useNavigate } from 'react-router-dom';
import {
  Badge,
  Button,
  Center,
  Group,
  Loader,
  Paper,
  Skeleton,
  Stack,
  Switch,
  Text,
  Title,
} from '@mantine/core';
import { IconArrowLeft } from '@tabler/icons-react';
import { usePlugin, usePluginDevices, useTogglePlugin } from '@/hooks/plugins';
import { PluginConfigForm } from '@/components/plugins/PluginConfigForm';

function PluginDevices({ pluginId }: { pluginId: string }) {
  const { data: devices, isLoading } = usePluginDevices(pluginId);
  if (isLoading) return <Skeleton h={16} w={200} />;
  if (!devices?.length) return <Text size="sm" c="dimmed">No devices</Text>;
  return (
    <Stack gap={4}>
      {devices.map((d) => (
        <Text key={d.id} size="sm">
          {d.name}
          {d.location && (
            <Text component="span" c="dimmed">
              {' '}
              — {d.location}
            </Text>
          )}
          <Badge size="xs" ml={8} color={d.is_online ? 'green' : 'gray'} variant="dot">
            {d.is_online ? 'online' : 'offline'}
          </Badge>
        </Text>
      ))}
    </Stack>
  );
}

export function PluginDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { data: plugin, isLoading } = usePlugin(id ?? '');
  const { mutate: toggle } = useTogglePlugin();

  if (isLoading) {
    return (
      <Center h="40vh">
        <Loader />
      </Center>
    );
  }
  if (!plugin) return <Text c="dimmed">Plugin not found</Text>;

  return (
    <Stack>
      <Button
        variant="subtle"
        leftSection={<IconArrowLeft size={14} />}
        onClick={() => navigate('/plugins')}
        w="fit-content"
      >
        Back
      </Button>

      <Paper p="md" withBorder>
        <Group justify="space-between" align="flex-start" wrap="nowrap">
          <Stack gap={4}>
            <Group gap="sm">
              <Title order={2}>{plugin.display_name}</Title>
              <Badge variant="light">{plugin.plugin_type}</Badge>
              <Text size="sm" c="dimmed" className="nl-mono">
                v{plugin.version}
              </Text>
            </Group>
            <Text size="xs" c="dimmed" className="nl-mono">
              {plugin.module_name}
            </Text>
          </Stack>
          <Group gap="xs">
            <Text size="sm" c="dimmed">
              Active
            </Text>
            <Switch
              checked={plugin.is_active}
              onChange={(e) =>
                toggle({ id: plugin.id, isActive: e.currentTarget.checked })
              }
            />
          </Group>
        </Group>
        {plugin.description && (
          <Text size="sm" c="dimmed" mt="sm" style={{ whiteSpace: 'pre-wrap' }}>
            {plugin.description}
          </Text>
        )}
      </Paper>

      {plugin.plugin_type === 'device' && (
        <Stack gap="xs">
          <Title order={4}>Devices</Title>
          <Paper p="md" withBorder>
            <PluginDevices pluginId={plugin.id} />
          </Paper>
        </Stack>
      )}

      <Stack gap="xs">
        <Group gap="xs" align="baseline">
          <Title order={4}>Configuration</Title>
          <Text size="xs" c="dimmed">
            Saving restarts the plugin automatically.
          </Text>
        </Group>
        <Paper p="md" withBorder>
          <PluginConfigForm pluginId={plugin.id} />
        </Paper>
      </Stack>
    </Stack>
  );
}
