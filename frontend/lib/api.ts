// Lightweight API client. Falls back to mock data when the backend isn't available
// so the dashboard works standalone. Once the FastAPI server is running, real data is used.

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function safeFetch<T>(path: string, fallback: T, init?: RequestInit): Promise<T> {
  try {
    const res = await fetch(`${BASE_URL}${path}`, {
      cache: "no-store",
      ...init,
      headers: { "Content-Type": "application/json", ...(init?.headers || {}) }
    });
    if (!res.ok) throw new Error(`Bad status ${res.status}`);
    return (await res.json()) as T;
  } catch {
    return fallback;
  }
}

export const api = {
  get: <T>(path: string, fallback: T) => safeFetch<T>(path, fallback),
  post: <T>(path: string, body: unknown, fallback: T) =>
    safeFetch<T>(path, fallback, { method: "POST", body: JSON.stringify(body) }),
  put: <T>(path: string, body: unknown, fallback: T) =>
    safeFetch<T>(path, fallback, { method: "PUT", body: JSON.stringify(body) })
};
