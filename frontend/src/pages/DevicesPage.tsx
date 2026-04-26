import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Title, Table, Badge, Text, Stack, Group, Select, SegmentedControl, Skeleton, Button } from '@mantine/core';
import { useDevices } from '@/hooks/devices';
import { usePlugins } from '@/hooks/plugins';

export function DevicesPage() {
  const navigate = useNavigate();
  const { data: plugins } = usePlugins();
  const [pluginFilter, setPluginFilter] = useState<string | null>(null);
  const [onlineFilter, setOnlineFilter] = useState('all');

  const isOnline = onlineFilter === 'online' ? true : onlineFilter === 'offline' ? false : undefined;
  const hasFilter = !!pluginFilter || onlineFilter !== 'all';
  const { data: devices, isLoading } = useDevices({
    plugin_id: pluginFilter ?? undefined,
    is_online: isOnline,
  });

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
          {isLoading ? (
            Array.from({ length: 5 }).map((_, i) => (
              <Table.Tr key={`skel-${i}`}>
                <Table.Td colSpan={5}><Skeleton h={20} /></Table.Td>
              </Table.Tr>
            ))
          ) : devices?.length ? (
            devices.map((device) => (
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
                <Table.Td>
                  <Text className="nl-mono">
                    {device.sensor_count}
                  </Text>
                </Table.Td>
                <Table.Td>
                  <Text size="sm" c="dimmed" className="nl-mono">
                    {device.last_seen ? new Date(device.last_seen).toLocaleString() : '—'}
                  </Text>
                </Table.Td>
              </Table.Tr>
            ))
          ) : (
            <Table.Tr>
              <Table.Td colSpan={5}>
                {hasFilter ? (
                  <Text c="dimmed" ta="center" py="md">No devices match these filters.</Text>
                ) : (
                  <Stack align="center" py="md" gap={6}>
                    <Text c="dimmed">No devices found.</Text>
                    <Text size="xs" c="dimmed">
                      Devices appear automatically when a plugin registers them.
                    </Text>
                    <Button size="xs" variant="default" onClick={() => navigate('/plugins')}>
                      Manage plugins
                    </Button>
                  </Stack>
                )}
              </Table.Td>
            </Table.Tr>
          )}
        </Table.Tbody>
      </Table>
    </Stack>
  );
}
