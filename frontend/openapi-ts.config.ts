import { defineConfig } from "@hey-api/openapi-ts";

export default defineConfig({
  input: "./openapi.json",
  output: {
    clean: true,
    path: "./src/api/client",
    postProcess: [],
  },
  plugins: [
    {
      name: "@hey-api/client-fetch",
      runtimeConfigPath: "./src/api/config.ts",
    },
    "@hey-api/typescript",
    "@hey-api/sdk",
  ],
});
