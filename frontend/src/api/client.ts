import { authEvents } from '@/lib/authEvents';

export function buildQueryString(params: Record<string, string | number | boolean | undefined | null>): string {
  const qs = new URLSearchParams();
  for (const [key, val] of Object.entries(params)) {
    if (val !== undefined && val !== null && val !== '') qs.set(key, String(val));
  }
  const s = qs.toString();
  return s ? `?${s}` : '';
}

async function extractErrorMessage(res: Response): Promise<string> {
  const ct = res.headers.get('content-type') ?? '';
  if (ct.includes('application/json')) {
    try {
      const body = await res.json();
      if (typeof body?.detail === 'string') return body.detail;
      if (Array.isArray(body?.detail)) {
        return body.detail
          .map((d: { loc?: unknown[]; msg?: string }) =>
            d.loc?.length ? `${d.loc.join('.')}: ${d.msg ?? ''}` : (d.msg ?? ''),
          )
          .filter(Boolean)
          .join('; ');
      }
      if (typeof body?.message === 'string') return body.message;
    } catch { /* fall through to statusText */ }
  }
  return res.statusText || 'Request failed';
}

export async function apiFetch<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(url, {
    credentials: 'include',
    ...options,
    headers: { 'Content-Type': 'application/json', ...options?.headers },
  });
  if (res.status === 401) {
    authEvents.emitUnauthorized();
    const detail = await extractErrorMessage(res);
    throw new Error(`401 ${detail}`);
  }
  if (!res.ok) {
    throw new Error(`${res.status} ${await extractErrorMessage(res)}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}
