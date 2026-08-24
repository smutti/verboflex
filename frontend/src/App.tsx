import { useCallback, useEffect, useRef, useState } from "react";

import { readHealthApiV1HealthGet } from "./api/client";

type ConnectionState = "error" | "loading" | "online";

const API_ERROR_COPY =
  "We could not reach the API. Check that the backend is running, then retry the connection.";

export function App() {
  const [connectionState, setConnectionState] =
    useState<ConnectionState>("loading");
  const requestVersion = useRef(0);

  const checkHealth = useCallback(async () => {
    const version = requestVersion.current + 1;
    requestVersion.current = version;
    setConnectionState("loading");

    try {
      const result = await readHealthApiV1HealthGet();

      if (requestVersion.current === version) {
        setConnectionState(
          result.data?.status === "ok" ? "online" : "error",
        );
      }
    } catch {
      if (requestVersion.current === version) {
        setConnectionState("error");
      }
    }
  }, []);

  useEffect(() => {
    void checkHealth();

    return () => {
      requestVersion.current += 1;
    };
  }, [checkHealth]);

  if (connectionState === "error") {
    return (
      <section role="alert">
        <p>{API_ERROR_COPY}</p>
        <button type="button" onClick={() => void checkHealth()}>
          Retry connection
        </button>
      </section>
    );
  }

  return (
    <p role="status">
      {connectionState === "online" ? "API online" : "Checking API connection"}
    </p>
  );
}
