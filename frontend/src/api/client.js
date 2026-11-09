const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "/api/";

async function request(path, options = {}) {
  const { headers, ...rest } = options;

  const response = await fetch(`${BASE_URL}${path}`, {
    ...rest,
    headers: {
      "Content-Type": "application/json",
      ...(headers ?? {}),
    },
  });

  if (!response.ok) {
    let message = `API request failed with status ${response.status}`;
    try {
      const errorBody = await response.json();
      if (errorBody && errorBody.detail) {
        message = errorBody.detail;
      }
    } catch {
      // Response body is not JSON; keep the default error message.
    }
    throw new Error(message);
  }

  if (response.status === 204) {
    return null;
  }

  return response.json();
}

export const apiClient = {
  get: (path) => request(path),
  post: (path, data) => request(path, { method: "POST", body: JSON.stringify(data) }),
  put: (path, data) => request(path, { method: "PUT", body: JSON.stringify(data) }),
  patch: (path, data) => request(path, { method: "PATCH", body: JSON.stringify(data) }),
  delete: (path) => request(path, { method: "DELETE" }),
};
