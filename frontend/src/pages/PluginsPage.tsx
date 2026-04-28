import { useNavigate } from 'react-router-dom';
import { Title, Table, Badge, Switch, Text, Skeleton, Stack } from '@mantine/core';
import { usePlugins, useTogglePlugin } from '@/hooks/plugins';

export function PluginsPage() {
  const { data: plugins, isLoading } = usePlugins();
  const { mutate: toggle } = useTogglePlugin();
  const navigate = useNavigate();

  return (
    <Stack>
      <Title order={2}>Plugins</Title>
      <Table highlightOnHover>
        <Table.Thead>
          <Table.Tr>
            <Table.Th>Name</Table.Th>
            <Table.Th>Type</Table.Th>
            <Table.Th>Version</Table.Th>
            <Table.Th>Devices</Table.Th>
            <Table.Th>Active</Table.Th>
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {isLoading ? (
            Array.from({ length: 3 }).map((_, i) => (
              <Table.Tr key={`skel-${i}`}>
                <Table.Td colSpan={5}><Skeleton h={20} /></Table.Td>
              </Table.Tr>
            ))
          ) : plugins?.length ? (
            plugins.map((plugin) => (
              <Table.Tr
                key={plugin.id}
                style={{ cursor: 'pointer' }}
                onClick={() => navigate(`/plugins/${plugin.id}`)}
              >
                <Table.Td fw={500}>{plugin.display_name}</Table.Td>
                <Table.Td><Badge variant="light" size="sm">{plugin.plugin_type}</Badge></Table.Td>
                <Table.Td>
                  <Text size="sm" c="dimmed" className="nl-mono">
                    {plugin.version}
                  </Text>
                </Table.Td>
                <Table.Td>
                  {plugin.plugin_type === 'device' ? (
                    <Text className="nl-mono">{plugin.device_count}</Text>
                  ) : (
                    <Text c="dimmed">—</Text>
                  )}
                </Table.Td>
                <Table.Td onClick={(e) => e.stopPropagation()}>
                  <Switch
                    checked={plugin.is_active}
                    onChange={(e) => toggle({ id: plugin.id, isActive: e.currentTarget.checked })}
                  />
                </Table.Td>
              </Table.Tr>
            ))
          ) : (
            <Table.Tr>
              <Table.Td colSpan={5}>
                <Stack align="center" py="md" gap={4}>
                  <Text c="dimmed">No plugins found.</Text>
                  <Text size="xs" c="dimmed">
                    Plugins register themselves on startup. Check the plugin worker logs if expected ones are missing.
                  </Text>
                </Stack>
              </Table.Td>
            </Table.Tr>
          )}
        </Table.Tbody>
      </Table>
    </Stack>
  );
}
