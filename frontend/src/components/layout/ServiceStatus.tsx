import { useCallback, useEffect, useRef, useState } from "react";

import {
  readSystemStatus,
  type SystemStatusResponse,
} from "../../api/client";
import { Badge } from "../ui/badge";
import { Button } from "../ui/button";
import { Alert, AlertDescription } from "../ui/alert";

export interface ServiceStatusProps {
  accessToken: string;
}

type StatusState =
  | { status: "loading" }
  | { status: "loaded"; data: SystemStatusResponse }
  | { status: "error" };

const API_ERROR_COPY =
  "We could not reach the API. Check that the backend is running, then retry the connection.";

export function ServiceStatus({ accessToken }: ServiceStatusProps) {
  const [state, setState] = useState<StatusState>({ status: "loading" });
  const requestVersion = useRef(0);

  const checkStatus = useCallback(async () => {
    const version = requestVersion.current + 1;
    requestVersion.current = version;
    setState({ status: "loading" });

    try {
      const result = await readSystemStatus({ auth: accessToken });
      if (requestVersion.current !== version) {
        return;
      }
      setState(
        result.data === undefined
          ? { status: "error" }
          : { status: "loaded", data: result.data },
      );
    } catch {
      if (requestVersion.current === version) {
        setState({ status: "error" });
      }
    }
  }, [accessToken]);

  useEffect(() => {
    void checkStatus();

    return () => {
      requestVersion.current += 1;
    };
  }, [checkStatus]);

  if (state.status === "loading") {
    return <p role="status">Checking service status</p>;
  }

  if (state.status === "error") {
    return (
      <Alert className="rounded-lg">
        <AlertDescription>
          <p>{API_ERROR_COPY}</p>
          <Button
            type="button"
            variant="outline"
            onClick={() => void checkStatus()}
          >
            Retry connection
          </Button>
        </AlertDescription>
      </Alert>
    );
  }

  const status = state.data;
  const services = [
    ["API", status.api],
    ["Database", status.database],
    ["Redis", status.redis],
    ["Worker", status.worker],
  ] as const;

  return (
    <section
      aria-labelledby="service-status-title"
      className="grid gap-4 border-y bg-secondary px-4 py-4"
    >
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2
          id="service-status-title"
          className="text-heading font-semibold"
        >
          Service status
        </h2>
        <p className="text-label text-muted-foreground">
          Last checked: <time dateTime={status.checked_at}>{status.checked_at}</time>
        </p>
      </div>
      <ul className="flex flex-wrap gap-2" aria-label="Platform services">
        {services.map(([name, state]) => (
          <li key={name}>
            <Badge
              variant="outline"
              className="rounded-md"
              data-service-state={state}
            >
              {name} {state}
            </Badge>
          </li>
        ))}
      </ul>
    </section>
  );
}
