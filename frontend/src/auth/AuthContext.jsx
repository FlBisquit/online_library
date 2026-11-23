import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { apiClient, clearTokens, getAccessToken, getRefreshToken, setTokens } from "../api/client";

const AuthContext = createContext(null);

const decodeTokenPayload = (token) => {
  try {
    const payload = token.split(".")[1];
    const base64 = payload.replace(/-/g, "+").replace(/_/g, "/");
    const json = decodeURIComponent(
      atob(base64)
        .split("")
        .map((c) => `%${`00${c.charCodeAt(0).toString(16)}`.slice(-2)}`)
        .join(""),
    );
    return JSON.parse(json);
  } catch {
    return {};
  }
};

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [initialized, setInitialized] = useState(false);

  const loadUser = useCallback(async (accessToken) => {
    const payload = decodeTokenPayload(accessToken);
    const me = await apiClient.get("/auth/me/");
    return {
      ...me,
      roles: me.groups ?? [],
      is_librarian: (me.groups ?? []).includes("librarian"),
      is_admin: (me.groups ?? []).includes("admin"),
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    const restore = async () => {
      if (getAccessToken()) {
        try {
          const userData = await loadUser(getAccessToken());
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
      const userData = await loadUser(data.access);
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

  const value = useMemo(
    () => ({ user, initialized, login, logout, setUser }),
    [user, initialized, login, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used within AuthProvider");
  return context;
};
