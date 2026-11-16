const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "/api/";

const ACCESS_TOKEN_KEY = "library_access_token";
const REFRESH_TOKEN_KEY = "library_refresh_token";

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

async function request(path, options = {}) {
  const { headers, ...rest } = options;

  const response = await fetch(`${BASE_URL}${path}`, {
    ...rest,
    headers: {
      "Content-Type": "application/json",
      ...(headers ?? {}),
      ...(getAccessToken() ? { Authorization: `Bearer ${getAccessToken()}` } : {}),
    },
  });

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
    let message = `API request failed with status ${response.status}`;
    if (data && typeof data === "object" && data.detail) {
      message = data.detail;
    }
    throw new Error(message);
  }

  if (response.status === 204) return null;
  return data;
}

export const apiClient = {
  get: (path, config) => request(path, { ...config, method: "GET" }),
  post: (path, data, config) => request(path, { method: "POST", body: JSON.stringify(data ?? {}), ...config }),
  put: (path, data, config) => request(path, { method: "PUT", body: JSON.stringify(data ?? {}), ...config }),
  patch: (path, data, config) => request(path, { method: "PATCH", body: JSON.stringify(data ?? {}), ...config }),
  delete: (path, config) => request(path, { method: "DELETE", ...config }),
};
