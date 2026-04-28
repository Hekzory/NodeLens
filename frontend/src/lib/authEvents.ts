// Tiny pub-sub so apiFetch can signal "401 received" without a circular
// import on the React/TanStack Query layer. Auth provider subscribes once
// at mount and flips the cached auth status to unauthenticated.

type Listener = () => void;
const listeners = new Set<Listener>();

export const authEvents = {
  emitUnauthorized(): void {
    for (const l of listeners) l();
  },
  onUnauthorized(listener: Listener): () => void {
    listeners.add(listener);
    return () => {
      listeners.delete(listener);
    };
  },
};
