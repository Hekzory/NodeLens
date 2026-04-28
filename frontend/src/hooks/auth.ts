import { useEffect } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import * as api from '@/api/auth';
import { authEvents } from '@/lib/authEvents';
import type { AuthStatus } from '@/types';

const AUTH_QK = ['auth', 'status'] as const;

export const useAuthStatus = () =>
  useQuery({
    queryKey: AUTH_QK,
    queryFn: ({ signal }) => api.fetchAuthStatus(signal),
    refetchInterval: false,
    refetchOnWindowFocus: false,
    staleTime: Infinity,
    retry: false,
  });

export function useUnauthorizedHandler(): void {
  const qc = useQueryClient();
  useEffect(() => {
    return authEvents.onUnauthorized(() => {
      qc.setQueryData<AuthStatus>(AUTH_QK, (prev) =>
        prev ? { ...prev, authenticated: false, user: null } : prev,
      );
      // Drop any cached protected-route data so the next render doesn't flash stale content.
      qc.removeQueries({ predicate: (q) => q.queryKey[0] !== 'auth' });
    });
  }, [qc]);
}

export const useLogin = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ username, password }: { username: string; password: string }) =>
      api.login(username, password),
    onSuccess: () => qc.invalidateQueries({ queryKey: AUTH_QK }),
    meta: { silent: true },
  });
};

export const useSetup = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ username, password }: { username: string; password: string }) =>
      api.setup(username, password),
    onSuccess: () => qc.invalidateQueries({ queryKey: AUTH_QK }),
    meta: { silent: true },
  });
};

export const useLogout = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.logout(),
    onSuccess: () => {
      qc.removeQueries({ predicate: (q) => q.queryKey[0] !== 'auth' });
      qc.invalidateQueries({ queryKey: AUTH_QK });
    },
  });
};

export const useChangePassword = () =>
  useMutation({
    mutationFn: ({ old_password, new_password }: { old_password: string; new_password: string }) =>
      api.changePassword(old_password, new_password),
  });
