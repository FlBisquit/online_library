import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { apiClient, clearTokens, getAccessToken, getRefreshToken, setTokens, setAuthLostHandler } from "../api/client";

const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [initialized, setInitialized] = useState(false);

  const loadUser = useCallback(async () => {
    const me = await apiClient.get("/auth/me/");
    return {
      ...me,
      roles: me.groups ?? [],
      is_librarian: (me.groups ?? []).includes("librarian"),
      is_admin: (me.groups ?? []).includes("admin"),
    };
  }, []);

  useEffect(() => {
    setAuthLostHandler(() => setUser(null));
    return () => setAuthLostHandler(null);
  }, []);

  useEffect(() => {
    let cancelled = false;
    const restore = async () => {
      if (getAccessToken()) {
        try {
          const userData = await loadUser();
          if (!cancelled) setUser(userData);
        } catch {
          // Сессия не восстановлена — показываем экран входа.
        }
      }
      if (!cancelled) setInitialized(true);
    };
    restore();
    return () => {
      cancelled = true;
    };
  }, [loadUser]);

  const login = useCallback(
    async (email, password) => {
      const data = await apiClient.post("/token/", { email, password });
      setTokens({ access: data.access, refresh: data.refresh });
      const userData = await loadUser();
      setUser(userData);
      return userData;
    },
    [loadUser],
  );

  const logout = useCallback(async () => {
    const refresh = getRefreshToken();
    if (refresh) {
      try {
        await apiClient.post("/token/blacklist/", { refresh });
      } catch {
        // Игнорируем ошибки при выходе.
      }
    }
    clearTokens();
    setUser(null);
  }, []);

  const register = useCallback(
    async ({ email, password, fullName, phone }) => {
      await apiClient.post("/auth/register/", { full_name: fullName, email, password, phone });
      return login(email, password);
    },
    [login],
  );

  const value = useMemo(
    () => ({ user, initialized, login, logout, register, setUser }),
    [user, initialized, login, logout, register],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used within AuthProvider");
  return context;
};
