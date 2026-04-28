import { Suspense, useState } from 'react';
import {
  ActionIcon,
  AppShell,
  Avatar,
  Burger,
  Center,
  Group,
  Loader,
  Menu,
  NavLink,
  Text,
  UnstyledButton,
} from '@mantine/core';
import { useDisclosure } from '@mantine/hooks';
import {
  IconBell,
  IconChevronDown,
  IconDevices,
  IconKey,
  IconLayoutDashboard,
  IconLogout,
  IconPlug,
  IconSettings,
  IconUsers,
} from '@tabler/icons-react';
import { Outlet, NavLink as RouterNavLink, useLocation } from 'react-router-dom';
import { Logo } from '@/components/Logo';
import { ChangePasswordModal } from '@/components/users/ChangePasswordModal';
import { useAuthStatus, useLogout } from '@/hooks/auth';

const navItems = [
  { label: 'Dashboard', icon: IconLayoutDashboard, to: '/' },
  { label: 'Devices', icon: IconDevices, to: '/devices' },
  { label: 'Alerts', icon: IconBell, to: '/alerts' },
  { label: 'Plugins', icon: IconPlug, to: '/plugins' },
  { label: 'Users', icon: IconUsers, to: '/users' },
  { label: 'Settings', icon: IconSettings, to: '/settings' },
];

function UserMenu() {
  const { data } = useAuthStatus();
  const logout = useLogout();
  const [pwOpen, setPwOpen] = useState(false);

  const username = data?.user?.username ?? '';
  const initial = username ? username[0]?.toUpperCase() : '?';

  return (
    <>
      <Menu position="bottom-end" withArrow withinPortal shadow="md">
        <Menu.Target>
          <UnstyledButton aria-label="Account menu">
            <Group gap="xs" wrap="nowrap">
              <Avatar size="sm" radius="xl" color="cyan">
                {initial}
              </Avatar>
              <Text size="sm" visibleFrom="sm" fw={500}>
                {username}
              </Text>
              <ActionIcon variant="subtle" color="gray" size="sm" component="span">
                <IconChevronDown size={14} />
              </ActionIcon>
            </Group>
          </UnstyledButton>
        </Menu.Target>
        <Menu.Dropdown>
          <Menu.Label>Signed in as {username}</Menu.Label>
          <Menu.Item
            leftSection={<IconKey size={14} />}
            onClick={() => setPwOpen(true)}
          >
            Change password
          </Menu.Item>
          <Menu.Divider />
          <Menu.Item
            leftSection={<IconLogout size={14} />}
            color="red"
            onClick={() => logout.mutate()}
            disabled={logout.isPending}
          >
            Log out
          </Menu.Item>
        </Menu.Dropdown>
      </Menu>
      <ChangePasswordModal opened={pwOpen} onClose={() => setPwOpen(false)} />
    </>
  );
}

export function AppLayout() {
  const location = useLocation();
  const [opened, { toggle, close }] = useDisclosure();

  return (
    <AppShell
      header={{ height: 50 }}
      navbar={{ width: 220, breakpoint: 'sm', collapsed: { mobile: !opened } }}
      padding="md"
    >
      <AppShell.Header>
        <Group h="100%" px="md" justify="space-between">
          <Group gap="sm">
            <Burger
              opened={opened}
              onClick={toggle}
              hiddenFrom="sm"
              size="sm"
              aria-label={opened ? 'Close navigation' : 'Open navigation'}
            />
            <Logo variant="lockup" size={28} />
            <Text size="xs" c="dimmed" visibleFrom="sm">IoT Telemetry Monitor</Text>
          </Group>
          <UserMenu />
        </Group>
      </AppShell.Header>
      <AppShell.Navbar p="sm">
        {navItems.map(({ label, icon: Icon, to }) => (
          <NavLink
            key={to}
            component={RouterNavLink}
            to={to}
            label={label}
            leftSection={<Icon size={18} />}
            active={to === '/' ? location.pathname === '/' || location.pathname.startsWith('/dashboards') : location.pathname.startsWith(to)}
            onClick={close}
          />
        ))}
      </AppShell.Navbar>
      <AppShell.Main>
        <Suspense fallback={<Center h="50vh"><Loader /></Center>}>
          <Outlet />
        </Suspense>
      </AppShell.Main>
    </AppShell>
  );
}
