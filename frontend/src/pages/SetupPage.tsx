import {
  Alert,
  Box,
  Button,
  Center,
  PasswordInput,
  Paper,
  Stack,
  Text,
  TextInput,
  Title,
} from '@mantine/core';
import { useForm } from '@mantine/form';
import { IconAlertCircle, IconShieldCheck } from '@tabler/icons-react';
import { useSetup } from '@/hooks/auth';

interface FormValues {
  username: string;
  password: string;
  confirmPassword: string;
}

export function SetupPage() {
  const setup = useSetup();
  const form = useForm<FormValues>({
    initialValues: { username: '', password: '', confirmPassword: '' },
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

  const handleSubmit = form.onSubmit(({ username, password }) => {
    setup.mutate({ username, password });
  });

  const errorMessage =
    setup.isError ? (setup.error instanceof Error ? setup.error.message : 'Setup failed') : null;

  return (
    <Center mih="100vh" p="md">
      <Paper p="xl" radius="md" shadow="md" w="100%" maw={460} withBorder>
        <Stack gap="lg">
          <Stack gap={4} align="center">
            <Box c="cyan">
              <IconShieldCheck size={40} />
            </Box>
            <Title order={2}>Welcome to NodeLens</Title>
            <Text size="sm" c="dimmed" ta="center">
              First-run setup. Create the administrator account that will manage
              this NodeLens deployment. You can add more users later.
            </Text>
          </Stack>

          <form onSubmit={handleSubmit}>
            <Stack gap="md">
              <TextInput
                label="Username"
                placeholder="admin"
                autoComplete="username"
                autoFocus
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
                <Alert
                  color="red"
                  variant="light"
                  icon={<IconAlertCircle size={16} />}
                  title="Setup failed"
                >
                  {errorMessage}
                </Alert>
              )}

              <Button type="submit" loading={setup.isPending} fullWidth>
                Create admin account
              </Button>
            </Stack>
          </form>
        </Stack>
      </Paper>
    </Center>
  );
}
