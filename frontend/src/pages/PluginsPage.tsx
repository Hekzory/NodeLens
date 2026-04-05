import { useState } from 'react';
import { Title, Table, Badge, Switch, Text, Collapse, Loader, Center, Stack, Box } from '@mantine/core';
import { usePlugins, usePluginDevices, useTogglePlugin } from '@/hooks/plugins';

function PluginDevices({ pluginId }: { pluginId: string }) {
  const { data: devices, isLoading } = usePluginDevices(pluginId);
  if (isLoading) return <Loader size="xs" />;
  if (!devices?.length) return <Text size="sm" c="dimmed" p="xs">No devices</Text>;
  return (
    <Box p="xs">
      {devices.map((d) => (
        <Text key={d.id} size="sm">
          {d.name}
          {d.location && <Text component="span" c="dimmed"> — {d.location}</Text>}
          <Badge size="xs" ml={8} color={d.is_online ? 'green' : 'gray'}>{d.is_online ? 'online' : 'offline'}</Badge>
        </Text>
      ))}
    </Box>
  );
}

export function PluginsPage() {
  const { data: plugins, isLoading } = usePlugins();
  const { mutate: toggle } = useTogglePlugin();
  const [expanded, setExpanded] = useState<string | null>(null);

  if (isLoading) return <Center h="40vh"><Loader /></Center>;

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
          {plugins?.map((plugin) => (
            <>
              <Table.Tr
                key={plugin.id}
                style={{ cursor: 'pointer' }}
                onClick={() => setExpanded(expanded === plugin.id ? null : plugin.id)}
              >
                <Table.Td fw={500}>{plugin.display_name}</Table.Td>
                <Table.Td><Badge variant="light" size="sm">{plugin.plugin_type}</Badge></Table.Td>
                <Table.Td><Text size="sm" c="dimmed">{plugin.version}</Text></Table.Td>
                <Table.Td>{plugin.device_count}</Table.Td>
                <Table.Td onClick={(e) => e.stopPropagation()}>
                  <Switch
                    checked={plugin.is_active}
                    onChange={(e) => toggle({ id: plugin.id, isActive: e.currentTarget.checked })}
                  />
                </Table.Td>
              </Table.Tr>
              <Table.Tr key={`${plugin.id}-expand`}>
                <Table.Td colSpan={5} p={0}>
                  <Collapse expanded={expanded === plugin.id}>
                    <PluginDevices pluginId={plugin.id} />
                  </Collapse>
                </Table.Td>
              </Table.Tr>
            </>
          ))}
        </Table.Tbody>
      </Table>
    </Stack>
  );
}
