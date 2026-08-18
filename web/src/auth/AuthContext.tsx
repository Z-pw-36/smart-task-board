import { useCallback, useEffect, useMemo, useState } from "react";

import { apiRequest, authExpiredEvent, session } from "../api/client";
import type { CurrentUser, LoginResponse } from "../api/types";
import { AuthContext } from "./auth-context";

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [loading, setLoading] = useState(() => Boolean(session.getToken()));

  const logout = useCallback(() => {
    session.clear();
    setUser(null);
    setLoading(false);
  }, []);

  const restore = useCallback(async () => {
    if (!session.getToken()) {
      setLoading(false);
      return;
    }
    try {
      setUser(await apiRequest<CurrentUser>("/api/v1/me"));
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
    const result = await apiRequest<LoginResponse>(
      "/api/v1/auth/prototype-login",
      { method: "POST", body: JSON.stringify({ employee_no: employeeNo }) },
      { anonymous: true },
    );
    session.setToken(result.access_token);
    try {
      setUser(await apiRequest<CurrentUser>("/api/v1/me"));
    } catch (error) {
      session.clear();
      throw error;
    }
  }, []);

  const value = useMemo(() => ({ user, loading, login, logout }), [user, loading, login, logout]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
