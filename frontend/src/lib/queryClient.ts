import { QueryClient } from '@tanstack/react-query';
import { notifications } from '@mantine/notifications';

const FALLBACK_POLLING_SECONDS = 10;

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchInterval: FALLBACK_POLLING_SECONDS * 1000,
      staleTime: 5_000,
      retry: 1,
    },
    mutations: {
      onError: (error, _vars, _onMutateResult, context) => {
        // Mutations can opt out via `meta: { silent: true }` (login/setup show
        // inline form errors instead of a global toast).
        if (context.meta?.silent) return;
        notifications.show({
          color: 'red',
          title: 'Action failed',
          message: error instanceof Error ? error.message : 'Unknown error',
        });
      },
    },
  },
});

/**
 * Update the dashboard polling cadence at runtime. Active observers pick up
 * the new interval on their next refetch tick — no page reload needed.
 *
 * Bound to the `frontend_polling_interval_seconds` system setting.
 */
export const applyPollingInterval = (seconds: number) => {
  if (!Number.isFinite(seconds) || seconds <= 0) return;
  queryClient.setDefaultOptions({
    queries: {
      refetchInterval: seconds * 1000,
      staleTime: 5_000,
      retry: 1,
    },
    mutations: queryClient.getDefaultOptions().mutations,
  });
};
