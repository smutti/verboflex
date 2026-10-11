import { useEffect, useState } from "react";
import { mcpRequest } from "./api";

export function useMcpData<T>(token: string, path: string) {
  const [revision, setRevision] = useState(0);
  const key = `${path}:${revision}`;
  const [result, setResult] = useState<{
    key: string;
    token: string;
    data?: T;
    error?: Error;
  }>();
  useEffect(() => {
    const controller = new AbortController();
    void mcpRequest<T>(token, path, { signal: controller.signal }).then(
      (data) => {
        if (!controller.signal.aborted) setResult({ key, token, data });
      },
      (error: Error) => {
        if (!controller.signal.aborted) setResult({ key, token, error });
      },
    );
    return () => controller.abort();
  }, [token, path, key]);
  const current =
    result?.key === key && result.token === token ? result : undefined;
  return {
    data: current?.data,
    error: current?.error,
    isPending: !current,
    refetch: () => setRevision((value) => value + 1),
  };
}
