import { Suspense } from 'react';
import { AppShell, Center, Loader, NavLink, Text, Burger, Group } from '@mantine/core';
import { useDisclosure } from '@mantine/hooks';
import { IconLayoutDashboard, IconDevices, IconPlug, IconActivity } from '@tabler/icons-react';
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
          <Group gap={8}>
            <IconActivity size={22} color="var(--mantine-primary-color-filled)" />
            <Text fw={700} size="lg" c="var(--mantine-primary-color-filled)">NodeLens</Text>
          </Group>
          <Text size="xs" c="dimmed" visibleFrom="sm">IoT Telemetry Monitor</Text>
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
