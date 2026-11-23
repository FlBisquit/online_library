const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "/api/";

const ACCESS_TOKEN_KEY = "library_access_token";
const REFRESH_TOKEN_KEY = "library_refresh_token";

let authLostHandler = null;
let refreshPromise = null;

export const setAuthLostHandler = (handler) => {
  authLostHandler = handler;
};

export const getAccessToken = () => localStorage.getItem(ACCESS_TOKEN_KEY);
export const getRefreshToken = () => localStorage.getItem(REFRESH_TOKEN_KEY);

export const setTokens = ({ access, refresh } = {}) => {
  if (access) localStorage.setItem(ACCESS_TOKEN_KEY, access);
  else localStorage.removeItem(ACCESS_TOKEN_KEY);
  if (refresh) localStorage.setItem(REFRESH_TOKEN_KEY, refresh);
  else localStorage.removeItem(REFRESH_TOKEN_KEY);
};

export const clearTokens = () => {
  localStorage.removeItem(ACCESS_TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
};

const buildUrl = (path, params) => {
  const search = new URLSearchParams();
  Object.entries(params ?? {}).forEach(([key, value]) => {
    if (value === undefined || value === null || value === "") return;
    search.append(key, String(value));
  });
  const query = search.toString();
  return `${BASE_URL}${path}${query ? `?${query}` : ""}`;
};

const extractErrorMessage = (data, status) => {
  if (!data) return `API request failed with status ${status}`;
  if (typeof data === "string") return data;
  if (typeof data.detail === "string") return data.detail;
  if (Array.isArray(data.detail) && data.detail.length) {
    return data.detail.map((item) => (typeof item === "string" ? item : JSON.stringify(item))).join(", ");
  }
  if (Array.isArray(data.non_field_errors) && data.non_field_errors.length) {
    return data.non_field_errors.join(", ");
  }
  const fieldMessages = Object.entries(data)
    .filter(([key]) => key !== "detail" && key !== "non_field_errors")
    .flatMap(([key, value]) =>
      Array.isArray(value)
        ? value.map((item) => `${key}: ${typeof item === "string" ? item : JSON.stringify(item)}`)
        : [`${key}: ${value}`],
    );
  if (fieldMessages.length) return fieldMessages.join(", ");
  return `API request failed with status ${status}`;
};

const refreshAccessToken = async () => {
  const refresh = getRefreshToken();
  if (!refresh) return null;
  if (!refreshPromise) {
    refreshPromise = (async () => {
      const data = await apiClient.post("/token/refresh/", { refresh });
      setTokens({ access: data.access, refresh: data.refresh ?? refresh });
      return data.access;
    })().finally(() => {
      refreshPromise = null;
    });
  }
  return refreshPromise;
};

async function request(path, options = {}) {
  const { headers, params, ...rest } = options;
  const url = buildUrl(path, params);
  const doFetch = async (token) =>
    fetch(url, {
      ...rest,
      headers: {
        "Content-Type": "application/json",
        ...(headers ?? {}),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
    });

  let response = await doFetch(getAccessToken());
  if (response.status === 401) {
    const newToken = await refreshAccessToken();
    if (!newToken) {
      clearTokens();
      if (authLostHandler) authLostHandler();
      throw new Error("Сессия истекла. Не удалось обновить токен.");
    }
    response = await doFetch(newToken);
    if (response.status === 401) {
      clearTokens();
      if (authLostHandler) authLostHandler();
      throw new Error("Сессия истекла. Повторная авторизация требуется.");
    }
  }

  const text = await response.text();
  let data = null;
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = text;
    }
  }
  if (!response.ok) {
    throw new Error(extractErrorMessage(data, response.status));
  }
  if (response.status === 204) return null;
  return data;
}

async function download(path, params) {
  const url = buildUrl(path, params);
  const response = await fetch(url, {
    method: "GET",
    headers: {
      ...(getAccessToken() ? { Authorization: `Bearer ${getAccessToken()}` } : {}),
    },
  });
  if (!response.ok) {
    const text = await response.text();
    let data = null;
    if (text) {
      try {
        data = JSON.parse(text);
      } catch {
        data = text;
      }
    }
    throw new Error(extractErrorMessage(data, response.status));
  }
  return await response.blob();
}

export const apiClient = {
  get: (path, config) => request(path, { ...config, method: "GET" }),
  post: (path, data, config) => request(path, { method: "POST", body: JSON.stringify(data ?? {}), ...config }),
  put: (path, data, config) => request(path, { method: "PUT", body: JSON.stringify(data ?? {}), ...config }),
  patch: (path, data, config) => request(path, { method: "PATCH", body: JSON.stringify(data ?? {}), ...config }),
  delete: (path, config) => request(path, { method: "DELETE", ...config }),
  download,
};
