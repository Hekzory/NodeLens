import { useState } from 'react';
import {
  ActionIcon,
  Badge,
  Button,
  Center,
  Group,
  Loader,
  Menu,
  Skeleton,
  Stack,
  Switch,
  Table,
  Text,
  Title,
  Tooltip,
} from '@mantine/core';
import { notifications } from '@mantine/notifications';
import {
  IconDotsVertical,
  IconKey,
  IconPlus,
  IconTrash,
  IconUserCheck,
  IconUserX,
} from '@tabler/icons-react';
import { useAuthStatus } from '@/hooks/auth';
import { useDeleteUser, useUpdateUser, useUsers } from '@/hooks/users';
import { UserCreateModal } from '@/components/users/UserCreateModal';
import { AdminResetPasswordModal } from '@/components/users/AdminResetPasswordModal';
import type { UserRead } from '@/types';

function relativeOrAbsolute(iso: string | null): string {
  if (!iso) return '—';
  const d = new Date(iso);
  return d.toLocaleString();
}

export function UsersPage() {
  const { data: status } = useAuthStatus();
  const { data: users, isLoading } = useUsers();
  const updateUser = useUpdateUser();
  const deleteUser = useDeleteUser();

  const [createOpen, setCreateOpen] = useState(false);
  const [resetTarget, setResetTarget] = useState<UserRead | null>(null);

  const meId = status?.user?.id ?? null;

  const handleToggleActive = (user: UserRead) => {
    updateUser.mutate(
      { id: user.id, data: { is_active: !user.is_active } },
      {
        onSuccess: () =>
          notifications.show({
            color: 'gray',
            title: user.is_active ? 'User deactivated' : 'User reactivated',
            message: user.username,
          }),
      },
    );
  };

  const handleDelete = (user: UserRead) => {
    if (!confirm(`Delete user "${user.username}"? This cannot be undone.`)) return;
    deleteUser.mutate(user.id, {
      onSuccess: () =>
        notifications.show({
          color: 'gray',
          title: 'User deleted',
          message: user.username,
        }),
    });
  };

  return (
    <Stack>
      <Group justify="space-between" align="flex-end">
        <Stack gap={4}>
          <Title order={2}>Users</Title>
          <Text size="sm" c="dimmed">
            Manage who can sign in to this NodeLens deployment. All users have
            full administrative access.
          </Text>
        </Stack>
        <Button
          leftSection={<IconPlus size={16} />}
          onClick={() => setCreateOpen(true)}
        >
          Add user
        </Button>
      </Group>

      <Table highlightOnHover>
        <Table.Thead>
          <Table.Tr>
            <Table.Th>Username</Table.Th>
            <Table.Th>Status</Table.Th>
            <Table.Th>Created</Table.Th>
            <Table.Th>Last sign-in</Table.Th>
            <Table.Th style={{ width: 1 }}>Active</Table.Th>
            <Table.Th style={{ width: 1 }} />
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
          ) : users?.length ? (
            users.map((u) => {
              const isMe = u.id === meId;
              return (
                <Table.Tr key={u.id}>
                  <Table.Td>
                    <Group gap="xs">
                      <Text fw={500}>{u.username}</Text>
                      {isMe && (
                        <Badge size="xs" variant="light" color="cyan">
                          you
                        </Badge>
                      )}
                    </Group>
                  </Table.Td>
                  <Table.Td>
                    {u.is_active ? (
                      <Badge color="green" variant="dot">
                        Active
                      </Badge>
                    ) : (
                      <Badge color="gray" variant="dot">
                        Disabled
                      </Badge>
                    )}
                  </Table.Td>
                  <Table.Td>
                    <Text size="sm" c="dimmed">
                      {relativeOrAbsolute(u.created_at)}
                    </Text>
                  </Table.Td>
                  <Table.Td>
                    <Text size="sm" c="dimmed">
                      {relativeOrAbsolute(u.last_login_at)}
                    </Text>
                  </Table.Td>
                  <Table.Td>
                    <Tooltip
                      label={isMe ? "You can't deactivate yourself" : ''}
                      disabled={!isMe}
                      withArrow
                    >
                      <Switch
                        checked={u.is_active}
                        disabled={isMe}
                        onChange={() => handleToggleActive(u)}
                      />
                    </Tooltip>
                  </Table.Td>
                  <Table.Td>
                    <Menu position="bottom-end" withinPortal>
                      <Menu.Target>
                        <ActionIcon variant="subtle" color="gray">
                          <IconDotsVertical size={16} />
                        </ActionIcon>
                      </Menu.Target>
                      <Menu.Dropdown>
                        <Menu.Item
                          leftSection={<IconKey size={14} />}
                          onClick={() => setResetTarget(u)}
                        >
                          Reset password
                        </Menu.Item>
                        <Menu.Item
                          leftSection={
                            u.is_active ? (
                              <IconUserX size={14} />
                            ) : (
                              <IconUserCheck size={14} />
                            )
                          }
                          disabled={isMe && u.is_active}
                          onClick={() => handleToggleActive(u)}
                        >
                          {u.is_active ? 'Deactivate' : 'Reactivate'}
                        </Menu.Item>
                        <Menu.Divider />
                        <Menu.Item
                          color="red"
                          leftSection={<IconTrash size={14} />}
                          disabled={isMe}
                          onClick={() => handleDelete(u)}
                        >
                          Delete user
                        </Menu.Item>
                      </Menu.Dropdown>
                    </Menu>
                  </Table.Td>
                </Table.Tr>
              );
            })
          ) : (
            <Table.Tr>
              <Table.Td colSpan={6}>
                <Center py="md">
                  <Loader size="sm" />
                </Center>
              </Table.Td>
            </Table.Tr>
          )}
        </Table.Tbody>
      </Table>

      <UserCreateModal opened={createOpen} onClose={() => setCreateOpen(false)} />
      <AdminResetPasswordModal
        opened={resetTarget !== null}
        onClose={() => setResetTarget(null)}
        userId={resetTarget?.id ?? null}
        username={resetTarget?.username ?? null}
      />
    </Stack>
  );
}
