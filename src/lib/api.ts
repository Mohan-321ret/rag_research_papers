// Authentication Module – shared fetch wrapper.
// Attaches the stored Bearer token to every request and centralizes 401
// (token missing/invalid/expired) handling: the token is cleared here and
// an `onUnauthorized` listener (wired up by AuthContext) is notified so
// React state gets cleared too, without api.ts needing to import React.

import { clearToken, getToken } from "./tokenStorage";

const API_BASE_URL =
  (import.meta.env.VITE_API_URL as string | undefined) || "http://localhost:8000/api/v1";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

type UnauthorizedListener = () => void;
let unauthorizedListener: UnauthorizedListener | null = null;

/** Registered once by AuthContext so any 401 (from any call, at any time)
 * clears the logged-in user, not just the ones AuthContext itself makes. */
export function onUnauthorized(listener: UnauthorizedListener): void {
  unauthorizedListener = listener;
}

interface RequestOptions {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  body?: unknown;
  /** Attach the stored Bearer token. Default true; pass false for
   * unauthenticated calls like /auth/login and /auth/register. */
  auth?: boolean;
}

export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = "GET", body, auth = true } = options;

  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (auth) {
    const token = getToken();
    if (token) headers.Authorization = `Bearer ${token}`;
  }

  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new ApiError(0, "Could not reach the server. Please check your connection.");
  }

  if (response.status === 401 && auth) {
    // Token was missing, invalid, or expired — the backend is the source of
    // truth here (this also catches expiry mid-session, not just on load).
    clearToken();
    unauthorizedListener?.();
  }

  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const data = await response.json();
      if (typeof data?.detail === "string") message = data.detail;
    } catch {
      // Non-JSON error body — keep the generic message.
    }
    throw new ApiError(response.status, message);
  }

  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}
