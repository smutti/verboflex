import type { CreateClientConfig } from "./client/client.gen";

const configuredBaseUrl = import.meta.env.VITE_API_BASE_URL?.trim();

export const createClientConfig: CreateClientConfig = (config) => ({
  ...config,
  baseUrl: configuredBaseUrl || "/",
  credentials: "include",
});
