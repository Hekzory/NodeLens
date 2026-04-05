import { AppShell, NavLink, Text, Box } from '@mantine/core';
import { IconLayoutDashboard, IconDevices, IconPlug } from '@tabler/icons-react';
import { Outlet, NavLink as RouterNavLink, useLocation } from 'react-router-dom';

const navItems = [
  { label: 'Dashboard', icon: IconLayoutDashboard, to: '/' },
  { label: 'Devices', icon: IconDevices, to: '/devices' },
  { label: 'Plugins', icon: IconPlug, to: '/plugins' },
];

export function AppLayout() {
  const location = useLocation();

  return (
    <AppShell navbar={{ width: 220, breakpoint: 'sm' }} padding="md">
      <AppShell.Navbar p="sm">
        <Box mb="md" px="xs">
          <Text fw={700} size="lg" c="blue">
            NodeLens
          </Text>
          <Text size="xs" c="dimmed">
            IoT Telemetry Monitor
          </Text>
        </Box>
        {navItems.map(({ label, icon: Icon, to }) => (
          <NavLink
            key={to}
            component={RouterNavLink}
            to={to}
            label={label}
            leftSection={<Icon size={18} />}
            active={to === '/' ? location.pathname === '/' : location.pathname.startsWith(to)}
          />
        ))}
      </AppShell.Navbar>
      <AppShell.Main>
        <Outlet />
      </AppShell.Main>
    </AppShell>
  );
}
