function isMissingPackagingCatalog(error) {
  const method = String(error?.config?.method || "get").toLowerCase();
  const url = String(error?.config?.url || "").toLowerCase();

  return method === "get"
    && error?.response?.status === 404
    && url.includes("packaging-types/");
}

export function installReferenceFallbacks(client) {
  client.interceptors.response.use(
    (response) => response,
    (error) => {
      if (!isMissingPackagingCatalog(error)) return Promise.reject(error);

      return Promise.resolve({
        ...(error.response || {}),
        data: [],
        status: 200,
        statusText: "OK",
        headers: error.response?.headers || {},
        config: error.config,
        request: error.request,
      });
    },
  );
}
