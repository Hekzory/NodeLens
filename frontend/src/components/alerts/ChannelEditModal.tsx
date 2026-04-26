import { Modal, TextInput, PasswordInput, NumberInput, Select, Checkbox, Button, Stack, Group, Textarea, Text } from '@mantine/core';
import { useForm } from '@mantine/form';
import { useEffect } from 'react';
import { usePlugins } from '@/hooks/plugins';
import type { NotificationChannel, NotificationChannelCreate } from '@/types';

interface Props {
  opened: boolean;
  onClose: () => void;
  onSubmit: (data: NotificationChannelCreate) => void;
  initial?: NotificationChannel;
  isPending?: boolean;
}

interface EmailConfig {
  to: string;
  smtp_host: string;
  smtp_port: number;
  from: string;
  subject: string;
  username: string;
  password: string;
  use_tls: boolean;
  start_tls: boolean;
}

interface FormValues {
  name: string;
  plugin_id: string;
  is_active: boolean;
  email: EmailConfig;
  rawJson: string;
}

const EMPTY: FormValues = {
  name: '',
  plugin_id: '',
  is_active: true,
  email: {
    to: '',
    smtp_host: '',
    smtp_port: 25,
    from: 'alerts@nodelens.local',
    subject: '',
    username: '',
    password: '',
    use_tls: false,
    start_tls: false,
  },
  rawJson: '{}',
};

export function ChannelEditModal({ opened, onClose, onSubmit, initial, isPending }: Props) {
  const { data: plugins } = usePlugins();
  const integrationPlugins = (plugins ?? []).filter((p) => p.plugin_type === 'integration');

  const form = useForm<FormValues>({ initialValues: EMPTY });

  const selected = integrationPlugins.find((p) => p.id === form.values.plugin_id);
  const isEmail = selected?.module_name === 'email';

  useEffect(() => {
    if (!opened) return;
    if (initial) {
      const cfg = (initial.config ?? {}) as Partial<EmailConfig> & Record<string, unknown>;
      form.setValues({
        name: initial.name,
        plugin_id: initial.plugin_id,
        is_active: initial.is_active,
        email: {
          to: typeof cfg.to === 'string' ? cfg.to : '',
          smtp_host: typeof cfg.smtp_host === 'string' ? cfg.smtp_host : '',
          smtp_port: typeof cfg.smtp_port === 'number' ? cfg.smtp_port : 25,
          from: typeof cfg.from === 'string' ? cfg.from : 'alerts@nodelens.local',
          subject: typeof cfg.subject === 'string' ? cfg.subject : '',
          username: typeof cfg.username === 'string' ? cfg.username : '',
          password: typeof cfg.password === 'string' ? cfg.password : '',
          use_tls: cfg.use_tls === true,
          start_tls: cfg.start_tls === true,
        },
        rawJson: JSON.stringify(initial.config ?? {}, null, 2),
      });
    } else {
      form.reset();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initial, opened]);

  const handleSubmit = form.onSubmit((values) => {
    let config: Record<string, unknown>;
    if (selected?.module_name === 'email') {
      config = {
        to: values.email.to,
        smtp_port: values.email.smtp_port,
        from: values.email.from,
      };
      if (values.email.smtp_host.trim()) config.smtp_host = values.email.smtp_host.trim();
      if (values.email.subject) config.subject = values.email.subject;
      if (values.email.username) config.username = values.email.username;
      if (values.email.password) config.password = values.email.password;
      if (values.email.use_tls) config.use_tls = true;
      if (values.email.start_tls) config.start_tls = true;
    } else {
      try {
        config = JSON.parse(values.rawJson || '{}');
      } catch {
        form.setFieldError('rawJson', 'Invalid JSON');
        return;
      }
    }
    onSubmit({
      name: values.name,
      plugin_id: values.plugin_id,
      is_active: values.is_active,
      config,
    });
  });

  return (
    <Modal
      opened={opened}
      onClose={onClose}
      title={initial ? 'Edit Channel' : 'New Channel'}
      size="md"
    >
      <form onSubmit={handleSubmit}>
        <Stack>
          <TextInput label="Name" required {...form.getInputProps('name')} />
          <Select
            label="Integration plugin"
            required
            data={integrationPlugins.map((p) => ({ value: p.id, label: p.display_name }))}
            value={form.values.plugin_id || null}
            onChange={(v) => form.setFieldValue('plugin_id', v ?? '')}
            placeholder={integrationPlugins.length ? 'Pick a plugin' : 'No integration plugins installed'}
          />

          {isEmail ? (
            <>
              <TextInput
                label="Recipient"
                required
                placeholder="user@example.com"
                value={form.values.email.to}
                onChange={(e) => form.setFieldValue('email.to', e.currentTarget.value)}
              />
              <TextInput
                label="SMTP host"
                placeholder="leave blank for direct MX delivery"
                description="Empty = look up the recipient's MX server and deliver directly. Set this to use a relay (e.g. a local catcher)."
                value={form.values.email.smtp_host}
                onChange={(e) => form.setFieldValue('email.smtp_host', e.currentTarget.value)}
              />
              <NumberInput
                label="SMTP port"
                min={1}
                max={65535}
                value={form.values.email.smtp_port}
                onChange={(v) =>
                  form.setFieldValue('email.smtp_port', typeof v === 'number' ? v : 25)
                }
              />
              <TextInput
                label="From"
                placeholder="alerts@nodelens.local"
                value={form.values.email.from}
                onChange={(e) => form.setFieldValue('email.from', e.currentTarget.value)}
              />
              <TextInput
                label="Subject (optional)"
                placeholder="Defaults to [NodeLens] {rule_name}"
                value={form.values.email.subject}
                onChange={(e) => form.setFieldValue('email.subject', e.currentTarget.value)}
              />
              <TextInput
                label="Username (optional)"
                placeholder="full email address for authenticated SMTP"
                description="Leave empty to send without auth (only works for direct-MX or open relays)."
                value={form.values.email.username}
                onChange={(e) => form.setFieldValue('email.username', e.currentTarget.value)}
              />
              <PasswordInput
                label="Password (optional)"
                placeholder="app password — never your real account password"
                value={form.values.email.password}
                onChange={(e) => form.setFieldValue('email.password', e.currentTarget.value)}
              />
              <Group grow>
                <Checkbox
                  label="Use TLS (port 465)"
                  checked={form.values.email.use_tls}
                  onChange={(e) => form.setFieldValue('email.use_tls', e.currentTarget.checked)}
                />
                <Checkbox
                  label="Use STARTTLS (port 587)"
                  checked={form.values.email.start_tls}
                  onChange={(e) => form.setFieldValue('email.start_tls', e.currentTarget.checked)}
                />
              </Group>
            </>
          ) : (
            <>
              <Text size="xs" c="dimmed">
                {selected
                  ? `Plugin '${selected.module_name}' has no specialised form — edit raw JSON config below.`
                  : 'Pick an integration plugin to configure its destination.'}
              </Text>
              <Textarea
                label="Config (JSON)"
                autosize
                minRows={5}
                styles={{ input: { fontFamily: 'monospace' } }}
                value={form.values.rawJson}
                onChange={(e) => form.setFieldValue('rawJson', e.currentTarget.value)}
                error={form.errors.rawJson}
              />
            </>
          )}

          <Checkbox label="Active" {...form.getInputProps('is_active', { type: 'checkbox' })} />

          <Group justify="flex-end">
            <Button variant="default" onClick={onClose}>Cancel</Button>
            <Button type="submit" loading={isPending}>{initial ? 'Save' : 'Create'}</Button>
          </Group>
        </Stack>
      </form>
    </Modal>
  );
}
