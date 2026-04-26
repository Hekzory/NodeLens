import { useState } from 'react';
import {
  Tabs,
  Title,
  Stack,
  Table,
  Badge,
  Switch,
  Text,
  Skeleton,
  Group,
  Button,
  ActionIcon,
  Tooltip,
  Box,
} from '@mantine/core';
import {
  IconAlertTriangle,
  IconBell,
  IconCheck,
  IconCircleCheck,
  IconCircleX,
  IconEdit,
  IconHistory,
  IconPlus,
  IconTrash,
} from '@tabler/icons-react';
import { notifications } from '@mantine/notifications';
import {
  useAcknowledgeAlert,
  useAlertHistory,
  useAlertRules,
  useChannels,
  useCreateAlertRule,
  useCreateChannel,
  useDeleteAlertRule,
  useDeleteChannel,
  useSetRuleChannels,
  useUpdateAlertRule,
  useUpdateChannel,
} from '@/hooks/alerts';
import { RuleEditModal } from '@/components/alerts/RuleEditModal';
import { ChannelEditModal } from '@/components/alerts/ChannelEditModal';
import type {
  AlertRule,
  AlertRuleCreate,
  NotificationChannel,
  NotificationChannelCreate,
} from '@/types';

const SEVERITY_COLOR: Record<string, string> = {
  info: 'blue',
  warning: 'yellow',
  critical: 'red',
};

function RulesTab() {
  const { data: rules, isLoading } = useAlertRules();
  const createRule = useCreateAlertRule();
  const updateRule = useUpdateAlertRule();
  const deleteRule = useDeleteAlertRule();
  const setRuleChannels = useSetRuleChannels();

  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<AlertRule | undefined>(undefined);

  const handleSubmit = (data: AlertRuleCreate, channelIds: string[]) => {
    if (editing) {
      updateRule.mutate(
        { id: editing.id, data },
        {
          onSuccess: (saved) => {
            setRuleChannels.mutate(
              { ruleId: saved.id, channelIds },
              {
                onSuccess: () => {
                  notifications.show({ color: 'green', title: 'Rule updated', message: saved.name });
                  setModalOpen(false);
                  setEditing(undefined);
                },
              },
            );
          },
        },
      );
    } else {
      createRule.mutate(data, {
        onSuccess: (saved) => {
          if (channelIds.length > 0) {
            setRuleChannels.mutate(
              { ruleId: saved.id, channelIds },
              {
                onSuccess: () => {
                  notifications.show({ color: 'green', title: 'Rule created', message: saved.name });
                  setModalOpen(false);
                },
              },
            );
          } else {
            notifications.show({ color: 'green', title: 'Rule created', message: saved.name });
            setModalOpen(false);
          }
        },
      });
    }
  };

  const handleDelete = (rule: AlertRule) => {
    if (!confirm(`Delete rule "${rule.name}"? This also clears its history.`)) return;
    deleteRule.mutate(rule.id, {
      onSuccess: () =>
        notifications.show({ color: 'gray', title: 'Rule deleted', message: rule.name }),
    });
  };

  return (
    <Stack>
      <Group justify="space-between">
        <Text c="dimmed" size="sm">
          {rules?.length ?? 0} rule{rules?.length === 1 ? '' : 's'}
        </Text>
        <Button
          leftSection={<IconPlus size={16} />}
          onClick={() => {
            setEditing(undefined);
            setModalOpen(true);
          }}
        >
          New rule
        </Button>
      </Group>

      <Table highlightOnHover>
        <Table.Thead>
          <Table.Tr>
            <Table.Th>Name</Table.Th>
            <Table.Th>Type</Table.Th>
            <Table.Th>Condition</Table.Th>
            <Table.Th>Severity</Table.Th>
            <Table.Th>Channels</Table.Th>
            <Table.Th>Active</Table.Th>
            <Table.Th />
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {isLoading ? (
            Array.from({ length: 3 }).map((_, i) => (
              <Table.Tr key={`skel-${i}`}>
                <Table.Td colSpan={7}>
                  <Skeleton h={20} />
                </Table.Td>
              </Table.Tr>
            ))
          ) : rules?.length ? (
            rules.map((rule) => (
              <Table.Tr key={rule.id}>
                <Table.Td fw={500}>{rule.name}</Table.Td>
                <Table.Td>
                  <Badge variant="light" size="sm">{rule.rule_type}</Badge>
                </Table.Td>
                <Table.Td>
                  <Text size="sm" className="nl-mono">
                    {rule.condition === 'no_data'
                      ? 'no_data'
                      : rule.rule_type === 'aggregated'
                        ? `${rule.aggregation}() ${rule.condition} ${rule.threshold}`
                        : `value ${rule.condition} ${rule.threshold}`}
                  </Text>
                </Table.Td>
                <Table.Td>
                  <Badge color={SEVERITY_COLOR[rule.severity] ?? 'gray'} variant="light">
                    {rule.severity}
                  </Badge>
                </Table.Td>
                <Table.Td>
                  <Text size="sm" className="nl-mono">{rule.channel_ids.length}</Text>
                </Table.Td>
                <Table.Td>
                  <Switch
                    checked={rule.is_active}
                    onChange={(e) =>
                      updateRule.mutate({
                        id: rule.id,
                        data: { is_active: e.currentTarget.checked },
                      })
                    }
                  />
                </Table.Td>
                <Table.Td>
                  <Group gap={4} justify="flex-end">
                    <Tooltip label="Edit">
                      <ActionIcon
                        variant="subtle"
                        onClick={() => {
                          setEditing(rule);
                          setModalOpen(true);
                        }}
                      >
                        <IconEdit size={16} />
                      </ActionIcon>
                    </Tooltip>
                    <Tooltip label="Delete">
                      <ActionIcon variant="subtle" color="red" onClick={() => handleDelete(rule)}>
                        <IconTrash size={16} />
                      </ActionIcon>
                    </Tooltip>
                  </Group>
                </Table.Td>
              </Table.Tr>
            ))
          ) : (
            <Table.Tr>
              <Table.Td colSpan={7}>
                <Stack align="center" py="md" gap={4}>
                  <Text c="dimmed">No alert rules yet.</Text>
                  <Text size="xs" c="dimmed">
                    Create one to start watching a sensor.
                  </Text>
                </Stack>
              </Table.Td>
            </Table.Tr>
          )}
        </Table.Tbody>
      </Table>

      <RuleEditModal
        opened={modalOpen}
        onClose={() => {
          setModalOpen(false);
          setEditing(undefined);
        }}
        onSubmit={handleSubmit}
        initial={editing}
        isPending={createRule.isPending || updateRule.isPending || setRuleChannels.isPending}
      />
    </Stack>
  );
}

function ChannelsTab() {
  const { data: channels, isLoading } = useChannels();
  const createCh = useCreateChannel();
  const updateCh = useUpdateChannel();
  const deleteCh = useDeleteChannel();

  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<NotificationChannel | undefined>(undefined);

  const handleSubmit = (data: NotificationChannelCreate) => {
    if (editing) {
      updateCh.mutate(
        { id: editing.id, data },
        {
          onSuccess: (saved) => {
            notifications.show({ color: 'green', title: 'Channel updated', message: saved.name });
            setModalOpen(false);
            setEditing(undefined);
          },
        },
      );
    } else {
      createCh.mutate(data, {
        onSuccess: (saved) => {
          notifications.show({ color: 'green', title: 'Channel created', message: saved.name });
          setModalOpen(false);
        },
      });
    }
  };

  const handleDelete = (ch: NotificationChannel) => {
    if (!confirm(`Delete channel "${ch.name}"? Linked rules will lose this delivery.`)) return;
    deleteCh.mutate(ch.id, {
      onSuccess: () =>
        notifications.show({ color: 'gray', title: 'Channel deleted', message: ch.name }),
    });
  };

  return (
    <Stack>
      <Group justify="space-between">
        <Text c="dimmed" size="sm">
          {channels?.length ?? 0} channel{channels?.length === 1 ? '' : 's'}
        </Text>
        <Button
          leftSection={<IconPlus size={16} />}
          onClick={() => {
            setEditing(undefined);
            setModalOpen(true);
          }}
        >
          New channel
        </Button>
      </Group>

      <Table highlightOnHover>
        <Table.Thead>
          <Table.Tr>
            <Table.Th>Name</Table.Th>
            <Table.Th>Plugin</Table.Th>
            <Table.Th>Destination</Table.Th>
            <Table.Th>Active</Table.Th>
            <Table.Th />
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {isLoading ? (
            Array.from({ length: 2 }).map((_, i) => (
              <Table.Tr key={`skel-${i}`}>
                <Table.Td colSpan={5}>
                  <Skeleton h={20} />
                </Table.Td>
              </Table.Tr>
            ))
          ) : channels?.length ? (
            channels.map((ch) => {
              const to = typeof ch.config?.to === 'string' ? (ch.config.to as string) : null;
              return (
                <Table.Tr key={ch.id}>
                  <Table.Td fw={500}>{ch.name}</Table.Td>
                  <Table.Td>
                    <Badge variant="light" size="sm">{ch.plugin_module_name ?? '—'}</Badge>
                  </Table.Td>
                  <Table.Td>
                    <Text size="sm" className="nl-mono">{to ?? '—'}</Text>
                  </Table.Td>
                  <Table.Td>
                    <Switch
                      checked={ch.is_active}
                      onChange={(e) =>
                        updateCh.mutate({ id: ch.id, data: { is_active: e.currentTarget.checked } })
                      }
                    />
                  </Table.Td>
                  <Table.Td>
                    <Group gap={4} justify="flex-end">
                      <Tooltip label="Edit">
                        <ActionIcon
                          variant="subtle"
                          onClick={() => {
                            setEditing(ch);
                            setModalOpen(true);
                          }}
                        >
                          <IconEdit size={16} />
                        </ActionIcon>
                      </Tooltip>
                      <Tooltip label="Delete">
                        <ActionIcon variant="subtle" color="red" onClick={() => handleDelete(ch)}>
                          <IconTrash size={16} />
                        </ActionIcon>
                      </Tooltip>
                    </Group>
                  </Table.Td>
                </Table.Tr>
              );
            })
          ) : (
            <Table.Tr>
              <Table.Td colSpan={5}>
                <Stack align="center" py="md" gap={4}>
                  <Text c="dimmed">No channels configured.</Text>
                  <Text size="xs" c="dimmed">
                    Channels link an integration plugin (e.g. email) to a destination.
                  </Text>
                </Stack>
              </Table.Td>
            </Table.Tr>
          )}
        </Table.Tbody>
      </Table>

      <ChannelEditModal
        opened={modalOpen}
        onClose={() => {
          setModalOpen(false);
          setEditing(undefined);
        }}
        onSubmit={handleSubmit}
        initial={editing}
        isPending={createCh.isPending || updateCh.isPending}
      />
    </Stack>
  );
}

function HistoryTab() {
  const { data: history, isLoading } = useAlertHistory({ limit: 100 });
  const ack = useAcknowledgeAlert();

  return (
    <Stack>
      <Text c="dimmed" size="sm">
        {history?.length ?? 0} fired alert{history?.length === 1 ? '' : 's'}
      </Text>
      <Table highlightOnHover>
        <Table.Thead>
          <Table.Tr>
            <Table.Th>When</Table.Th>
            <Table.Th>Rule</Table.Th>
            <Table.Th>Value</Table.Th>
            <Table.Th>Message</Table.Th>
            <Table.Th>Status</Table.Th>
            <Table.Th />
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {isLoading ? (
            Array.from({ length: 3 }).map((_, i) => (
              <Table.Tr key={`skel-${i}`}>
                <Table.Td colSpan={6}>
                  <Skeleton h={20} />
                </Table.Td>
              </Table.Tr>
            ))
          ) : history?.length ? (
            history.map((h) => (
              <Table.Tr key={h.id}>
                <Table.Td>
                  <Text size="sm">{new Date(h.triggered_at).toLocaleString()}</Text>
                </Table.Td>
                <Table.Td fw={500}>{h.rule_name ?? '—'}</Table.Td>
                <Table.Td>
                  <Text className="nl-mono" size="sm">
                    {h.triggered_value !== null ? h.triggered_value : '—'}
                  </Text>
                </Table.Td>
                <Table.Td>
                  <Text size="sm" lineClamp={2}>{h.message}</Text>
                </Table.Td>
                <Table.Td>
                  {h.acknowledged_at ? (
                    <Badge color="green" variant="light" leftSection={<IconCircleCheck size={12} />}>
                      acked
                    </Badge>
                  ) : (
                    <Badge color="orange" variant="light" leftSection={<IconCircleX size={12} />}>
                      open
                    </Badge>
                  )}
                </Table.Td>
                <Table.Td>
                  {!h.acknowledged_at && (
                    <Tooltip label="Acknowledge">
                      <ActionIcon
                        variant="subtle"
                        onClick={() => ack.mutate(h.id)}
                        loading={ack.isPending && ack.variables === h.id}
                      >
                        <IconCheck size={16} />
                      </ActionIcon>
                    </Tooltip>
                  )}
                </Table.Td>
              </Table.Tr>
            ))
          ) : (
            <Table.Tr>
              <Table.Td colSpan={6}>
                <Box ta="center" py="md">
                  <Text c="dimmed">No alerts have fired yet.</Text>
                </Box>
              </Table.Td>
            </Table.Tr>
          )}
        </Table.Tbody>
      </Table>
    </Stack>
  );
}

export function AlertsPage() {
  return (
    <Stack>
      <Title order={2}>Alerts</Title>
      <Tabs defaultValue="rules">
        <Tabs.List>
          <Tabs.Tab value="rules" leftSection={<IconAlertTriangle size={16} />}>Rules</Tabs.Tab>
          <Tabs.Tab value="channels" leftSection={<IconBell size={16} />}>Channels</Tabs.Tab>
          <Tabs.Tab value="history" leftSection={<IconHistory size={16} />}>History</Tabs.Tab>
        </Tabs.List>

        <Tabs.Panel value="rules" pt="md"><RulesTab /></Tabs.Panel>
        <Tabs.Panel value="channels" pt="md"><ChannelsTab /></Tabs.Panel>
        <Tabs.Panel value="history" pt="md"><HistoryTab /></Tabs.Panel>
      </Tabs>
    </Stack>
  );
}
