import { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Stack, Title, Text, Badge, Group, Table, Collapse, Button, Loader, Center, Paper,
} from '@mantine/core';
import { IconArrowLeft } from '@tabler/icons-react';
import { AreaChart } from '@mantine/charts';
import { useDevice } from '@/hooks/devices';
import { useDeviceTelemetry, useTelemetrySeries } from '@/hooks/telemetry';

function SensorChart({ sensorId }: { sensorId: string }) {
  const { data, isLoading } = useTelemetrySeries(sensorId);
  if (isLoading) return <Loader size="xs" />;
  if (!data?.points.length) return <Text size="sm" c="dimmed">No telemetry data</Text>;

  const chartData = data.points.map((p) => ({
    time: new Date(p.time).toLocaleTimeString(),
    value: p.value_numeric ?? 0,
  }));

  return (
    <AreaChart
      h={160}
      data={chartData}
      dataKey="time"
      series={[{ name: 'value', color: 'blue.6' }]}
      curveType="monotone"
      withDots={false}
      withLegend={false}
      tickLine="x"
    />
  );
}

export function DeviceDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { data: device, isLoading: devLoading } = useDevice(id!);
  const { data: telemetry } = useDeviceTelemetry(id!);
  const [expandedSensor, setExpandedSensor] = useState<string | null>(null);

  if (devLoading) return <Center h="40vh"><Loader /></Center>;
  if (!device) return <Text c="dimmed">Device not found</Text>;

  const latestBysensor = Object.fromEntries(
    (telemetry?.readings ?? []).map((r) => [r.sensor_id, r])
  );

  return (
    <Stack>
      <Button variant="subtle" leftSection={<IconArrowLeft size={14} />} onClick={() => navigate('/devices')} w="fit-content">
        Back
      </Button>
      <Paper p="md" withBorder>
        <Group justify="space-between">
          <div>
            <Title order={2}>{device.name}</Title>
            {device.location && <Text c="dimmed">{device.location}</Text>}
          </div>
          <Badge color={device.is_online ? 'green' : 'gray'} size="lg" variant="dot">
            {device.is_online ? 'Online' : 'Offline'}
          </Badge>
        </Group>
        {device.last_seen && (
          <Text size="sm" c="dimmed" mt="xs">Last seen: {new Date(device.last_seen).toLocaleString()}</Text>
        )}
      </Paper>

      <Title order={4}>Sensors</Title>
      <Table highlightOnHover>
        <Table.Thead>
          <Table.Tr>
            <Table.Th>Sensor</Table.Th>
            <Table.Th>Latest Value</Table.Th>
            <Table.Th>Unit</Table.Th>
            <Table.Th>Updated</Table.Th>
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {device.sensors.map((sensor) => {
            const latest = latestBysensor[sensor.id];
            return (
              <>
                <Table.Tr
                  key={sensor.id}
                  style={{ cursor: 'pointer' }}
                  onClick={() => setExpandedSensor(expandedSensor === sensor.id ? null : sensor.id)}
                >
                  <Table.Td fw={500}>{sensor.name}</Table.Td>
                  <Table.Td>
                    <Text fw={600}>{latest?.value_numeric?.toFixed(2) ?? '—'}</Text>
                  </Table.Td>
                  <Table.Td><Text c="dimmed">{sensor.unit ?? '—'}</Text></Table.Td>
                  <Table.Td>
                    <Text size="sm" c="dimmed">
                      {latest?.time ? new Date(latest.time).toLocaleTimeString() : '—'}
                    </Text>
                  </Table.Td>
                </Table.Tr>
                <Table.Tr key={`${sensor.id}-chart`}>
                  <Table.Td colSpan={4} p={0}>
                    <Collapse expanded={expandedSensor === sensor.id}>
                      <Stack p="md">
                        <SensorChart sensorId={sensor.id} />
                      </Stack>
                    </Collapse>
                  </Table.Td>
                </Table.Tr>
              </>
            );
          })}
        </Table.Tbody>
      </Table>
    </Stack>
  );
}
