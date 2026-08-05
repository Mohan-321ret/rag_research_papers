// Authentication Module – global auth state.
// Owns the logged-in user, session restore/validation on load, and the
// login/register/logout actions. LoginPage, ProtectedRoute, and TopBar all
// consume this via useAuth() instead of touching tokens or API calls directly.
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import { apiRequest, ApiError, onUnauthorized } from "@/lib/api";
import { clearToken, getToken, isTokenExpired, setToken } from "@/lib/tokenStorage";

export interface AuthUser {
  id: string;
  email: string;
  full_name: string | null;
  created_at: string;
}

interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: AuthUser;
}

interface AuthContextValue {
  user: AuthUser | null;
  isAuthenticated: boolean;
  /** True until the initial session-restore check (on page load) finishes. */
  isLoading: boolean;
  error: string | null;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, fullName?: string) => Promise<void>;
  logout: () => void;
  clearError: () => void;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const logout = useCallback(() => {
    clearToken();
    setUser(null);
  }, []);

  // Restore/validate the session once on load: a token in storage is only
  // trusted after (a) a client-side expiry check and (b) the backend
  // confirming it via /auth/me — a token could be expired, or for a user
  // that no longer exists.
  useEffect(() => {
    const token = getToken();
    if (!token || isTokenExpired(token)) {
      clearToken();
      setIsLoading(false);
      return;
    }
    apiRequest<AuthUser>("/auth/me")
      .then((u) => setUser(u))
      .catch(() => clearToken())
      .finally(() => setIsLoading(false));
  }, []);

  // Any API call (not just ones AuthContext makes) that gets a 401 mid-session
  // (token expired while the app was open) should also clear the logged-in user.
  useEffect(() => {
    onUnauthorized(() => setUser(null));
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    setError(null);
    try {
      const data = await apiRequest<TokenResponse>("/auth/login", {
        method: "POST",
        body: { email, password },
        auth: false,
      });
      setToken(data.access_token);
      setUser(data.user);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to sign in. Please try again.");
      throw err;
    }
  }, []);

  const register = useCallback(async (email: string, password: string, fullName?: string) => {
    setError(null);
    try {
      const data = await apiRequest<TokenResponse>("/auth/register", {
        method: "POST",
        body: { email, password, full_name: fullName || undefined },
        auth: false,
      });
      setToken(data.access_token);
      setUser(data.user);
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Unable to create your account. Please try again."
      );
      throw err;
    }
  }, []);

  const clearError = useCallback(() => setError(null), []);

  return (
    <AuthContext.Provider
      value={{
        user,
        isAuthenticated: !!user,
        isLoading,
        error,
        login,
        register,
        logout,
        clearError,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within an AuthProvider");
  return ctx;
}
