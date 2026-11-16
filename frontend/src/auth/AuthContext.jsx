import { createContext, useCallback, useContext, useMemo, useState } from "react";
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
    const userId = payload.user_id ?? payload.sub;
    if (!userId) return null;
    const reader = await apiClient.get(`/readers/${userId}/`);
    return {
      ...reader,
      roles: reader.groups ?? [],
      is_librarian: (reader.groups ?? []).includes("librarian"),
      is_admin: (reader.groups ?? []).includes("admin"),
    };
  }, []);

  const login = useCallback(
    async (email, password) => {
      const data = await apiClient.post("/token/", { email, password });
      setTokens({ access: data.access, refresh: data.refresh });
      const user = await loadUser(data.access);
      setUser(user);
      return user;
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
