// Authentication Module – JWT storage + client-side expiry check.
// A thin wrapper around localStorage so the storage key/mechanism lives in
// exactly one place (api.ts and AuthContext both import this instead of
// touching localStorage directly).

const TOKEN_KEY = "scholarai_access_token";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

interface JwtPayload {
  sub?: string;
  exp?: number;
}

/** Decode a JWT's payload without verifying its signature (client-side
 * expiry check only — the backend is the source of truth on every request). */
function decodeJwtPayload(token: string): JwtPayload | null {
  try {
    const base64Url = token.split(".")[1];
    if (!base64Url) return null;
    const base64 = base64Url.replace(/-/g, "+").replace(/_/g, "/");
    const json = decodeURIComponent(
      atob(base64)
        .split("")
        .map((c) => "%" + c.charCodeAt(0).toString(16).padStart(2, "0"))
        .join("")
    );
    return JSON.parse(json) as JwtPayload;
  } catch {
    return null;
  }
}

/** True if the token is missing an exp claim, malformed, or already expired. */
export function isTokenExpired(token: string): boolean {
  const payload = decodeJwtPayload(token);
  if (!payload?.exp) return true;
  return Date.now() >= payload.exp * 1000;
}
