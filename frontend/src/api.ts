// Cliente de la API. El token (si el servidor lo exige) se guarda solo en este navegador.
const TOKEN_KEY = "ytauto.token";

export function getToken(): string {
  try {
    return localStorage.getItem(TOKEN_KEY) ?? "";
  } catch {
    return "";
  }
}

export function setToken(token: string): void {
  try {
    localStorage.setItem(TOKEN_KEY, token);
  } catch {
    /* almacenamiento no disponible */
  }
}

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  const res = await fetch(path, { method, headers, body: body === undefined ? undefined : JSON.stringify(body) });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const j = await res.json();
      detail = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail);
    } catch {
      /* sin cuerpo JSON */
    }
    throw new ApiError(res.status, detail);
  }
  return (await res.json()) as T;
}

export const api = {
  get: <T,>(p: string) => request<T>("GET", p),
  post: <T,>(p: string, b?: unknown) => request<T>("POST", p, b ?? {}),
  put: <T,>(p: string, b: unknown) => request<T>("PUT", p, b),
  patch: <T,>(p: string, b: unknown) => request<T>("PATCH", p, b),
  del: <T,>(p: string) => request<T>("DELETE", p),
};

export function fileUrl(projectId: string, rel: string): string {
  const t = getToken();
  return `/api/projects/${projectId}/files/${rel}${t ? `?token=${encodeURIComponent(t)}` : ""}`;
}

export function wsUrl(): string {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  const t = getToken();
  return `${proto}://${location.host}/ws${t ? `?token=${encodeURIComponent(t)}` : ""}`;
}
