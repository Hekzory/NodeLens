import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Title, Table, Badge, Text, Stack, Group, Select, SegmentedControl, Loader, Center } from '@mantine/core';
import { useDevices } from '@/hooks/devices';
import { usePlugins } from '@/hooks/plugins';

export function DevicesPage() {
  const navigate = useNavigate();
  const { data: plugins } = usePlugins();
  const [pluginFilter, setPluginFilter] = useState<string | null>(null);
  const [onlineFilter, setOnlineFilter] = useState('all');

  const isOnline = onlineFilter === 'online' ? true : onlineFilter === 'offline' ? false : undefined;
  const { data: devices, isLoading } = useDevices({
    plugin_id: pluginFilter ?? undefined,
    is_online: isOnline,
  });

  if (isLoading) return <Center h="40vh"><Loader /></Center>;

  return (
    <Stack>
      <Group justify="space-between">
        <Title order={2}>Devices</Title>
        <Group>
          <Select
            placeholder="All plugins"
            clearable
            data={(plugins ?? []).map((p) => ({ value: p.id, label: p.display_name }))}
            value={pluginFilter}
            onChange={setPluginFilter}
            w={180}
          />
          <SegmentedControl
            data={[{ label: 'All', value: 'all' }, { label: 'Online', value: 'online' }, { label: 'Offline', value: 'offline' }]}
            value={onlineFilter}
            onChange={setOnlineFilter}
          />
        </Group>
      </Group>
      <Table highlightOnHover>
        <Table.Thead>
          <Table.Tr>
            <Table.Th>Name</Table.Th>
            <Table.Th>Location</Table.Th>
            <Table.Th>Status</Table.Th>
            <Table.Th>Sensors</Table.Th>
            <Table.Th>Last Seen</Table.Th>
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {devices?.map((device) => (
            <Table.Tr
              key={device.id}
              style={{ cursor: 'pointer' }}
              onClick={() => navigate(`/devices/${device.id}`)}
            >
              <Table.Td fw={500}>{device.name}</Table.Td>
              <Table.Td><Text size="sm" c="dimmed">{device.location ?? '—'}</Text></Table.Td>
              <Table.Td>
                <Badge color={device.is_online ? 'green' : 'red'} variant="dot">
                  {device.is_online ? 'Online' : 'Offline'}
                </Badge>
              </Table.Td>
              <Table.Td>{device.sensor_count}</Table.Td>
              <Table.Td>
                <Text size="sm" c="dimmed">
                  {device.last_seen ? new Date(device.last_seen).toLocaleString() : '—'}
                </Text>
              </Table.Td>
            </Table.Tr>
          ))}
          {!devices?.length && (
            <Table.Tr>
              <Table.Td colSpan={5}><Text c="dimmed" ta="center" py="md">No devices found</Text></Table.Td>
            </Table.Tr>
          )}
        </Table.Tbody>
      </Table>
    </Stack>
  );
}
