import { useEffect, useState } from "react";

import { readHealthApiV1HealthGet } from "./api/client";

export function App() {
  const [connectionCopy, setConnectionCopy] = useState(
    "Checking API connection",
  );

  useEffect(() => {
    let isActive = true;

    void readHealthApiV1HealthGet().then((result) => {
      if (isActive && result.data?.status === "ok") {
        setConnectionCopy("API online");
      }
    });

    return () => {
      isActive = false;
    };
  }, []);

  return <p role="status">{connectionCopy}</p>;
}
