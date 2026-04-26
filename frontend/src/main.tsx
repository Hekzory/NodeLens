import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { MantineProvider } from '@mantine/core';
import { Notifications, notifications } from '@mantine/notifications';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import '@mantine/core/styles.css';
import '@mantine/charts/styles.css';
import '@mantine/notifications/styles.css';
import './tokens.css';
import App from './App';
import { theme } from './theme';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchInterval: 10_000,
      staleTime: 5_000,
      retry: 1,
    },
    mutations: {
      onError: (error) => {
        notifications.show({
          color: 'red',
          title: 'Action failed',
          message: error instanceof Error ? error.message : 'Unknown error',
        });
      },
    },
  },
});

if (import.meta.env.DEV) {
  // Dev helper: run `__nlNotify()` in DevTools console to verify wiring.
  Object.assign(window, {
    __nlNotify: (opts?: Parameters<typeof notifications.show>[0]) =>
      notifications.show({
        color: 'cyan',
        title: 'Test',
        message: 'Notifications are wired',
        ...opts,
      }),
  });
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <MantineProvider theme={theme} forceColorScheme="dark">
        <Notifications />
        <App />
      </MantineProvider>
    </QueryClientProvider>
  </StrictMode>,
);
