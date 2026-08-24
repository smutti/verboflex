import { useEffect } from "react";

import { readSystemStatus } from "../../api/client";

export interface ServiceStatusProps {
  accessToken: string;
}

export function ServiceStatus({ accessToken }: ServiceStatusProps) {
  useEffect(() => {
    void readSystemStatus({ auth: accessToken }).catch(() => undefined);
  }, [accessToken]);

  return <p role="status">Checking service status</p>;
}
