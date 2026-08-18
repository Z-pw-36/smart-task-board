const TOKEN_KEY = "smarttaskboard.prototype.token";
const AUTH_EXPIRED_EVENT = "smarttaskboard:auth-expired";

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly code: string,
    message: string,
    public readonly details: Record<string, unknown> = {},
  ) {
    super(message);
  }
}

export const session = {
  getToken: () => sessionStorage.getItem(TOKEN_KEY),
  setToken: (token: string) => sessionStorage.setItem(TOKEN_KEY, token),
  clear: () => sessionStorage.removeItem(TOKEN_KEY),
};

export const authExpiredEvent = AUTH_EXPIRED_EVENT;

function apiBaseUrl(): string {
  return (import.meta.env.VITE_API_BASE_URL || "http://localhost:8000").replace(/\/$/, "");
}

function safeMessage(status: number): string {
  if (status === 409) return "任务已被其他操作更新，请刷新后重试。";
  if (status >= 500) return "服务暂时不可用，请稍后重试。";
  return "请求未能完成，请检查输入后重试。";
}

export async function apiRequest<T>(
  path: string,
  init: RequestInit = {},
  options: { anonymous?: boolean } = {},
): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  const token = session.getToken();
  if (!options.anonymous && token) headers.set("Authorization", `Bearer ${token}`);

  const response = await fetch(`${apiBaseUrl()}${path}`, { ...init, headers });
  if (!response.ok) {
    let code = "request_failed";
    let message = safeMessage(response.status);
    let details: Record<string, unknown> = {};
    try {
      const payload = (await response.json()) as {
        error?: { code?: string; message?: string; details?: Record<string, unknown> };
      };
      code = payload.error?.code || code;
      message = response.status >= 500 ? safeMessage(response.status) : payload.error?.message || message;
      details = payload.error?.details || details;
    } catch {
      // Deliberately hide non-JSON server bodies and internal stack traces.
    }
    if (response.status === 401 && !options.anonymous) {
      session.clear();
      window.dispatchEvent(new Event(AUTH_EXPIRED_EVENT));
    }
    throw new ApiError(response.status, code, message, details);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}
