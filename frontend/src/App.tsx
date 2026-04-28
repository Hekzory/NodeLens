import { lazy } from 'react';
import { Center, Loader } from '@mantine/core';
import {
  Navigate,
  Outlet,
  RouterProvider,
  createBrowserRouter,
} from 'react-router-dom';
import { AppLayout } from '@/components/AppLayout';
import { useAuthStatus, useUnauthorizedHandler } from '@/hooks/auth';

const DashboardPage = lazy(() => import('@/pages/DashboardPage').then(m => ({ default: m.DashboardPage })));
const DevicesPage = lazy(() => import('@/pages/DevicesPage').then(m => ({ default: m.DevicesPage })));
const DeviceDetailPage = lazy(() => import('@/pages/DeviceDetailPage').then(m => ({ default: m.DeviceDetailPage })));
const PluginsPage = lazy(() => import('@/pages/PluginsPage').then(m => ({ default: m.PluginsPage })));
const PluginDetailPage = lazy(() => import('@/pages/PluginDetailPage').then(m => ({ default: m.PluginDetailPage })));
const AlertsPage = lazy(() => import('@/pages/AlertsPage').then(m => ({ default: m.AlertsPage })));
const SystemSettingsPage = lazy(() => import('@/pages/SystemSettingsPage').then(m => ({ default: m.SystemSettingsPage })));
const LoginPage = lazy(() => import('@/pages/LoginPage').then(m => ({ default: m.LoginPage })));
const SetupPage = lazy(() => import('@/pages/SetupPage').then(m => ({ default: m.SetupPage })));
const UsersPage = lazy(() => import('@/pages/UsersPage').then(m => ({ default: m.UsersPage })));

function FullScreenLoader() {
  return (
    <Center h="100vh">
      <Loader />
    </Center>
  );
}

function AuthGate() {
  const { data, isLoading } = useAuthStatus();
  if (isLoading && !data) return <FullScreenLoader />;
  if (!data) return <FullScreenLoader />;
  if (data.setup_required) return <Navigate to="/setup" replace />;
  if (!data.authenticated) return <Navigate to="/login" replace />;
  return <AppLayout />;
}

function PublicGate({ for: target }: { for: 'login' | 'setup' }) {
  const { data, isLoading } = useAuthStatus();
  if (isLoading && !data) return <FullScreenLoader />;
  if (!data) return <FullScreenLoader />;
  if (data.authenticated) return <Navigate to="/" replace />;
  if (target === 'login' && data.setup_required) return <Navigate to="/setup" replace />;
  if (target === 'setup' && !data.setup_required) return <Navigate to="/login" replace />;
  return <Outlet />;
}

const router = createBrowserRouter([
  {
    element: <PublicGate for="login" />,
    children: [{ path: '/login', element: <LoginPage /> }],
  },
  {
    element: <PublicGate for="setup" />,
    children: [{ path: '/setup', element: <SetupPage /> }],
  },
  {
    element: <AuthGate />,
    children: [
      { path: '/', element: <DashboardPage /> },
      { path: '/dashboards/:id', element: <DashboardPage /> },
      { path: '/devices', element: <DevicesPage /> },
      { path: '/devices/:id', element: <DeviceDetailPage /> },
      { path: '/plugins', element: <PluginsPage /> },
      { path: '/plugins/:id', element: <PluginDetailPage /> },
      { path: '/alerts', element: <AlertsPage /> },
      { path: '/users', element: <UsersPage /> },
      { path: '/settings', element: <SystemSettingsPage /> },
    ],
  },
]);

export default function App() {
  // Always-on listener: any apiFetch 401 flips the cached auth status to
  // unauthenticated, which causes the router to redirect to /login on the
  // next render. Mounted above the router so it survives gate unmounts.
  useUnauthorizedHandler();
  return <RouterProvider router={router} />;
}
