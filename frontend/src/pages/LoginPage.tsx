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
import { IconAlertCircle, IconLock } from '@tabler/icons-react';
import { useLogin } from '@/hooks/auth';

interface FormValues {
  username: string;
  password: string;
}

export function LoginPage() {
  const login = useLogin();
  const form = useForm<FormValues>({
    initialValues: { username: '', password: '' },
    validate: {
      username: (v) => (v.trim() ? null : 'Username is required'),
      password: (v) => (v.length >= 1 ? null : 'Password is required'),
    },
  });

  const handleSubmit = form.onSubmit((values) => {
    login.mutate(values);
  });

  const errorMessage =
    login.isError ? (login.error instanceof Error ? login.error.message : 'Login failed') : null;

  return (
    <Center mih="100vh" p="md">
      <Paper p="xl" radius="md" shadow="md" w="100%" maw={420} withBorder>
        <Stack gap="lg">
          <Stack gap={4} align="center">
            <Box c="cyan">
              <IconLock size={36} />
            </Box>
            <Title order={2}>Sign in to NodeLens</Title>
            <Text size="sm" c="dimmed">
              Enter your credentials to continue.
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
                placeholder="Your password"
                autoComplete="current-password"
                required
                {...form.getInputProps('password')}
              />

              {errorMessage && (
                <Alert
                  color="red"
                  variant="light"
                  icon={<IconAlertCircle size={16} />}
                  title="Sign-in failed"
                >
                  {errorMessage}
                </Alert>
              )}

              <Button type="submit" loading={login.isPending} fullWidth>
                Sign in
              </Button>
            </Stack>
          </form>
        </Stack>
      </Paper>
    </Center>
  );
}
