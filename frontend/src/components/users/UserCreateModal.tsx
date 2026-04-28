import {
  Alert,
  Button,
  Group,
  Modal,
  PasswordInput,
  Stack,
  TextInput,
} from '@mantine/core';
import { useForm } from '@mantine/form';
import { IconAlertCircle } from '@tabler/icons-react';
import { useEffect } from 'react';
import { useCreateUser } from '@/hooks/users';

interface FormValues {
  username: string;
  password: string;
  confirmPassword: string;
}

const EMPTY: FormValues = { username: '', password: '', confirmPassword: '' };

interface Props {
  opened: boolean;
  onClose: () => void;
}

export function UserCreateModal({ opened, onClose }: Props) {
  const create = useCreateUser();
  const form = useForm<FormValues>({
    initialValues: EMPTY,
    validate: {
      username: (v) => {
        if (v.trim().length < 3) return 'Username must be at least 3 characters';
        if (!/^[A-Za-z0-9_.\-]+$/.test(v)) return 'Allowed characters: letters, digits, _ . -';
        return null;
      },
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
      create.reset();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [opened]);

  const handleSubmit = form.onSubmit(({ username, password }) => {
    create.mutate(
      { username, password },
      { onSuccess: () => onClose() },
    );
  });

  const errorMessage =
    create.isError ? (create.error instanceof Error ? create.error.message : 'Failed to create user') : null;

  return (
    <Modal opened={opened} onClose={onClose} title="Add user" size="sm">
      <form onSubmit={handleSubmit}>
        <Stack>
          <TextInput
            label="Username"
            placeholder="alice"
            autoComplete="off"
            required
            {...form.getInputProps('username')}
          />
          <PasswordInput
            label="Password"
            placeholder="At least 8 characters"
            autoComplete="new-password"
            required
            {...form.getInputProps('password')}
          />
          <PasswordInput
            label="Confirm password"
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
            <Button type="submit" loading={create.isPending}>
              Create
            </Button>
          </Group>
        </Stack>
      </form>
    </Modal>
  );
}
