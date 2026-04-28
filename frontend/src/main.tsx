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
import { fetchAuthStatus } from '@/api/auth';

// Bootstrap before mounting React:
//  • dashboard polling cadence (DB-backed system setting)
//  • auth status (so the router renders the right shell on first paint and
//    avoids flashing /login while the in-app fetch is still in flight)
// If either call fails we fall through with sensible defaults — the app
// still renders, the router will refetch /api/auth/status if needed, and
// the polling fallback is the hardcoded value in queryClient.ts.
async function bootstrap() {
  const [settingsResult, statusResult] = await Promise.allSettled([
    fetchSystemSettings(),
    fetchAuthStatus(),
  ]);

  if (settingsResult.status === 'fulfilled') {
    const polling = settingsResult.value.find(
      (s) => s.key === 'frontend_polling_interval_seconds',
    );
    if (polling && typeof polling.value === 'number') {
      applyPollingInterval(polling.value);
    }
  }

  if (statusResult.status === 'fulfilled') {
    queryClient.setQueryData(['auth', 'status'], statusResult.value);
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
