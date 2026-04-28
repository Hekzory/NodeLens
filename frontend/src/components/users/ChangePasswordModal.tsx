import {
  Alert,
  Button,
  Group,
  Modal,
  PasswordInput,
  Stack,
} from '@mantine/core';
import { useForm } from '@mantine/form';
import { notifications } from '@mantine/notifications';
import { IconAlertCircle } from '@tabler/icons-react';
import { useEffect } from 'react';
import { useChangePassword } from '@/hooks/auth';

interface FormValues {
  oldPassword: string;
  password: string;
  confirmPassword: string;
}

const EMPTY: FormValues = { oldPassword: '', password: '', confirmPassword: '' };

interface Props {
  opened: boolean;
  onClose: () => void;
}

export function ChangePasswordModal({ opened, onClose }: Props) {
  const change = useChangePassword();
  const form = useForm<FormValues>({
    initialValues: EMPTY,
    validate: {
      oldPassword: (v) => (v.length >= 1 ? null : 'Current password is required'),
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
      change.reset();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [opened]);

  const handleSubmit = form.onSubmit(({ oldPassword, password }) => {
    change.mutate(
      { old_password: oldPassword, new_password: password },
      {
        onSuccess: () => {
          notifications.show({
            color: 'green',
            title: 'Password changed',
            message: 'Your password has been updated.',
          });
          onClose();
        },
      },
    );
  });

  const errorMessage =
    change.isError ? (change.error instanceof Error ? change.error.message : 'Failed to change password') : null;

  return (
    <Modal opened={opened} onClose={onClose} title="Change password" size="sm">
      <form onSubmit={handleSubmit}>
        <Stack>
          <PasswordInput
            label="Current password"
            autoComplete="current-password"
            required
            autoFocus
            {...form.getInputProps('oldPassword')}
          />
          <PasswordInput
            label="New password"
            placeholder="At least 8 characters"
            autoComplete="new-password"
            required
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
            <Button type="submit" loading={change.isPending}>
              Change password
            </Button>
          </Group>
        </Stack>
      </form>
    </Modal>
  );
}
