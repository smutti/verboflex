import { useEffect } from "react";

import { readHealthApiV1HealthGet } from "./api/client";

export function App() {
  useEffect(() => {
    void readHealthApiV1HealthGet();
  }, []);

  return <p role="status">Checking API connection</p>;
}
