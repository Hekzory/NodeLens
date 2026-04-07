import { AppShell, NavLink, Text, Burger, Group } from '@mantine/core';
import { useDisclosure } from '@mantine/hooks';
import { IconLayoutDashboard, IconDevices, IconPlug } from '@tabler/icons-react';
import { Outlet, NavLink as RouterNavLink, useLocation } from 'react-router-dom';

const navItems = [
  { label: 'Dashboard', icon: IconLayoutDashboard, to: '/' },
  { label: 'Devices', icon: IconDevices, to: '/devices' },
  { label: 'Plugins', icon: IconPlug, to: '/plugins' },
];

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
        <Group h="100%" px="md">
          <Burger opened={opened} onClick={toggle} hiddenFrom="sm" size="sm" />
          <Text fw={700} size="lg" c="blue">NodeLens</Text>
          <Text size="xs" c="dimmed">IoT Telemetry Monitor</Text>
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
            active={to === '/' ? location.pathname === '/' : location.pathname.startsWith(to)}
            onClick={close}
          />
        ))}
      </AppShell.Navbar>
      <AppShell.Main>
        <Outlet />
      </AppShell.Main>
    </AppShell>
  );
}
