export const extractFieldErrors = (error) => {
  const data = error?.data;
  if (!data || typeof data !== "object") return {};
  const result = {};
  Object.entries(data).forEach(([key, value]) => {
    if (key === "detail" || key === "non_field_errors") return;
    if (Array.isArray(value)) result[key] = value.join(" ");
    else if (typeof value === "string") result[key] = value;
  });
  return result;
};

export const extractGeneralError = (error) => {
  const data = error?.data;
  if (!data || typeof data !== "object") return error?.message ?? null;
  if (typeof data.detail === "string") return data.detail;
  if (Array.isArray(data.non_field_errors) && data.non_field_errors.length) {
    return data.non_field_errors.join(" ");
  }
  return error?.message ?? null;
};
