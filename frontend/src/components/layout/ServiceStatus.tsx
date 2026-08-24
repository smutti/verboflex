import { useEffect, useState } from "react";

import {
  readSystemStatus,
  type SystemStatusResponse,
} from "../../api/client";
import { Badge } from "../ui/badge";

export interface ServiceStatusProps {
  accessToken: string;
}

export function ServiceStatus({ accessToken }: ServiceStatusProps) {
  const [status, setStatus] = useState<SystemStatusResponse | null>(null);

  useEffect(() => {
    let active = true;

    void readSystemStatus({ auth: accessToken })
      .then((result) => {
        if (active && result.data !== undefined) {
          setStatus(result.data);
        }
      })
      .catch(() => undefined);

    return () => {
      active = false;
    };
  }, [accessToken]);

  if (status === null) {
    return <p role="status">Checking service status</p>;
  }

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
