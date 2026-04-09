import { lazy } from 'react';
import { createBrowserRouter, RouterProvider } from 'react-router-dom';
import { AppLayout } from '@/components/AppLayout';

const DashboardPage = lazy(() => import('@/pages/DashboardPage').then(m => ({ default: m.DashboardPage })));
const DevicesPage = lazy(() => import('@/pages/DevicesPage').then(m => ({ default: m.DevicesPage })));
const DeviceDetailPage = lazy(() => import('@/pages/DeviceDetailPage').then(m => ({ default: m.DeviceDetailPage })));
const PluginsPage = lazy(() => import('@/pages/PluginsPage').then(m => ({ default: m.PluginsPage })));

const router = createBrowserRouter([
  {
    element: <AppLayout />,
    children: [
      { path: '/', element: <DashboardPage /> },
      { path: '/dashboards/:id', element: <DashboardPage /> },
      { path: '/devices', element: <DevicesPage /> },
      { path: '/devices/:id', element: <DeviceDetailPage /> },
      { path: '/plugins', element: <PluginsPage /> },
    ],
  },
]);

export default function App() {
  return <RouterProvider router={router} />;
}
