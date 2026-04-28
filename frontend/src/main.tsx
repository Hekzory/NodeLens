import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { MantineProvider } from '@mantine/core';
import { Notifications, notifications } from '@mantine/notifications';
import { QueryClientProvider } from '@tanstack/react-query';
import '@mantine/core/styles.css';
import '@mantine/charts/styles.css';
import '@mantine/notifications/styles.css';
import './tokens.css';
import App from './App';
import { theme } from './theme';
import { applyPollingInterval, queryClient } from '@/lib/queryClient';
import { fetchSystemSettings } from '@/api/systemSettings';

// Bootstrap the dashboard polling cadence from the DB-backed setting before
// mounting React. If the call fails (offline / fresh DB) we keep the fallback
// hardcoded in queryClient.ts so the app still renders.
async function bootstrap() {
  try {
    const settings = await fetchSystemSettings();
    const polling = settings.find((s) => s.key === 'frontend_polling_interval_seconds');
    if (polling && typeof polling.value === 'number') {
      applyPollingInterval(polling.value);
    }
  } catch {
    /* leave fallback in place */
  }

  if (import.meta.env.DEV) {
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
}

bootstrap();
