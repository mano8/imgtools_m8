export const getApiUrl = (url?: string): string => {
  const baseUrl = import.meta.env.VITE_API_URL;
  return baseUrl && url ? `${baseUrl}${url}` : '';
};
