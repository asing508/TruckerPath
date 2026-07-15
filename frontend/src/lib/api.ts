// In local dev, .env.local sets this to http://localhost:8000. In any build
// where the env var is absent (e.g. a plain Vercel deploy), fall back to the
// deployed Railway backend so the hosted frontend works without extra config.
export const API_URL =
  process.env.NEXT_PUBLIC_API_URL ??
  "https://truckerpath-production.up.railway.app";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText} on ${path}`);
  return res.json() as Promise<T>;
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, {
      method: "POST",
      body: body === undefined ? undefined : JSON.stringify(body),
    }),
};

export const fileUrl = (path: string) => `${API_URL}${path}`;
