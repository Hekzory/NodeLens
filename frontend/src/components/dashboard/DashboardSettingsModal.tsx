import { Modal, TextInput, Textarea, Checkbox, Button, Stack, Group } from '@mantine/core';
import { useForm } from '@mantine/form';
import { useEffect } from 'react';
import type { Dashboard, DashboardCreate } from '@/types';

interface Props {
  opened: boolean;
  onClose: () => void;
  onSubmit: (data: DashboardCreate) => void;
  initial?: Dashboard;
  isPending?: boolean;
}

export function DashboardSettingsModal({ opened, onClose, onSubmit, initial, isPending }: Props) {
  const form = useForm<DashboardCreate>({
    initialValues: { name: '', description: '', is_default: false },
  });

  const { setValues, reset } = form;

  useEffect(() => {
    if (initial) {
      setValues({ name: initial.name, description: initial.description ?? '', is_default: initial.is_default });
    } else {
      reset();
    }
  }, [initial, opened, setValues, reset]);

  return (
    <Modal opened={opened} onClose={onClose} title={initial ? 'Edit Dashboard' : 'New Dashboard'} size="sm">
      <form onSubmit={form.onSubmit(onSubmit)}>
        <Stack>
          <TextInput label="Name" placeholder="My Dashboard" required {...form.getInputProps('name')} />
          <Textarea label="Description" placeholder="Optional description" autosize {...form.getInputProps('description')} />
          <Checkbox label="Set as default dashboard" {...form.getInputProps('is_default', { type: 'checkbox' })} />
          <Group justify="flex-end">
            <Button variant="default" onClick={onClose}>Cancel</Button>
            <Button type="submit" loading={isPending}>{initial ? 'Save' : 'Create'}</Button>
          </Group>
        </Stack>
      </form>
    </Modal>
  );
}
