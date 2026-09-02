import { useCallback, useEffect, useMemo, useState } from "react";

import { authExpiredEvent, session } from "../api/client";
import { getCurrentUser, issueAuthTokens, refreshAuthTokens, revokeRefreshToken } from "../api/endpoints";
import type { CurrentUser } from "../api/types";
import { AuthContext } from "./auth-context";

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [loading, setLoading] = useState(() => Boolean(session.getToken()));

  const logout = useCallback(() => {
    const refreshToken = session.getRefreshToken();
    session.clear();
    setUser(null);
    setLoading(false);
    if (refreshToken) void revokeRefreshToken({ refresh_token: refreshToken }).catch(() => undefined);
  }, []);

  const restore = useCallback(async () => {
    if (!session.getToken() && !session.getRefreshToken()) {
      setLoading(false);
      return;
    }
    try {
      if (!session.getToken()) {
        const refreshToken = session.getRefreshToken();
        if (!refreshToken) {
          setLoading(false);
          return;
        }
        const rotated = await refreshAuthTokens({ refresh_token: refreshToken });
        session.setTokens(rotated.access_token, rotated.refresh_token);
      }
      setUser(await getCurrentUser());
    } catch {
      logout();
    } finally {
      setLoading(false);
    }
  }, [logout]);

  useEffect(() => {
    void restore();
  }, [restore]);

  useEffect(() => {
    const expire = () => logout();
    window.addEventListener(authExpiredEvent, expire);
    return () => window.removeEventListener(authExpiredEvent, expire);
  }, [logout]);

  const login = useCallback(async (employeeNo: string) => {
    const result = await issueAuthTokens({ employee_no: employeeNo });
    session.setTokens(result.access_token, result.refresh_token);
    try {
      setUser(await getCurrentUser());
    } catch (error) {
      session.clear();
      throw error;
    }
  }, []);

  const value = useMemo(() => ({ user, loading, login, logout }), [user, loading, login, logout]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
