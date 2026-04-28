import {
  Alert,
  Button,
  Group,
  Modal,
  PasswordInput,
  Stack,
  Text,
} from '@mantine/core';
import { useForm } from '@mantine/form';
import { IconAlertCircle } from '@tabler/icons-react';
import { useEffect } from 'react';
import { useAdminResetPassword } from '@/hooks/users';

interface FormValues {
  password: string;
  confirmPassword: string;
}

const EMPTY: FormValues = { password: '', confirmPassword: '' };

interface Props {
  opened: boolean;
  onClose: () => void;
  userId: string | null;
  username: string | null;
}

export function AdminResetPasswordModal({ opened, onClose, userId, username }: Props) {
  const reset = useAdminResetPassword();
  const form = useForm<FormValues>({
    initialValues: EMPTY,
    validate: {
      password: (v) => {
        if (v.length < 8) return 'Password must be at least 8 characters';
        if (v.length > 72) return 'Password must be at most 72 characters';
        return null;
      },
      confirmPassword: (v, values) =>
        v === values.password ? null : 'Passwords do not match',
    },
  });

  useEffect(() => {
    if (opened) {
      form.setValues(EMPTY);
      form.resetDirty();
      reset.reset();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [opened]);

  const handleSubmit = form.onSubmit(({ password }) => {
    if (!userId) return;
    reset.mutate(
      { id: userId, newPassword: password },
      { onSuccess: () => onClose() },
    );
  });

  const errorMessage =
    reset.isError ? (reset.error instanceof Error ? reset.error.message : 'Failed to reset password') : null;

  return (
    <Modal opened={opened} onClose={onClose} title="Reset password" size="sm">
      <form onSubmit={handleSubmit}>
        <Stack>
          <Text size="sm" c="dimmed">
            Set a new password for <Text component="span" fw={600}>{username ?? '—'}</Text>.
            They will need to use the new password the next time they sign in.
          </Text>
          <PasswordInput
            label="New password"
            placeholder="At least 8 characters"
            autoComplete="new-password"
            required
            autoFocus
            {...form.getInputProps('password')}
          />
          <PasswordInput
            label="Confirm new password"
            autoComplete="new-password"
            required
            {...form.getInputProps('confirmPassword')}
          />
          {errorMessage && (
            <Alert color="red" variant="light" icon={<IconAlertCircle size={16} />}>
              {errorMessage}
            </Alert>
          )}
          <Group justify="flex-end">
            <Button variant="default" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" loading={reset.isPending} disabled={!userId}>
              Reset password
            </Button>
          </Group>
        </Stack>
      </form>
    </Modal>
  );
}
