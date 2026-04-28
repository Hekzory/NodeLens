import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import * as api from '@/api/users';
import type { UserCreate, UserUpdate } from '@/types';

const USERS_QK = ['users'] as const;

export const useUsers = () =>
  useQuery({
    queryKey: USERS_QK,
    queryFn: ({ signal }) => api.fetchUsers(signal),
  });

export const useCreateUser = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: UserCreate) => api.createUser(data),
    onSuccess: () => qc.invalidateQueries({ queryKey: USERS_QK }),
  });
};

export const useUpdateUser = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: UserUpdate }) => api.updateUser(id, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: USERS_QK }),
  });
};

export const useDeleteUser = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.deleteUser(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: USERS_QK }),
  });
};

export const useAdminResetPassword = () =>
  useMutation({
    mutationFn: ({ id, newPassword }: { id: string; newPassword: string }) =>
      api.adminResetPassword(id, newPassword),
  });
