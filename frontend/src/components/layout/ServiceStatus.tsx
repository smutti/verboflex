import { t, useUiLanguage } from "@/i18n";
import { useEffect, useRef, useState } from "react";
import {
  Activity,
  CheckCircle2,
  Clock3,
  Cpu,
  Database,
  Layers3,
  TriangleAlert,
  type LucideIcon,
} from "lucide-react";

import { readSystemStatus, type SystemStatusResponse } from "../../api/client";
import { Badge } from "../ui/badge";
import { Button } from "../ui/button";
import { Alert, AlertDescription } from "../ui/alert";

export interface ServiceStatusProps {
  accessToken: string;
  prominent?: boolean;
}

type StatusState =
  | { status: "loading" }
  | { status: "loaded"; data: SystemStatusResponse }
  | { status: "error" };

const API_ERROR_COPY =
  "We could not reach the API. Check that the backend is running, then retry the connection.";

type ServiceState = SystemStatusResponse[
  "api" | "database" | "redis" | "worker"];

interface StatePresentation {
  Icon: LucideIcon;
  label: string;
  surfaceClassName: string;
  textClassName: string;
}

const STATE_PRESENTATION: Record<ServiceState, StatePresentation> = {
  online: {
    Icon: CheckCircle2,
    get label() {
      return t("Online");
    },
    surfaceClassName: "border-success/40 bg-success/10",
    textClassName: "text-success",
  },
  pending: {
    Icon: Clock3,
    get label() {
      return t("Pending");
    },
    surfaceClassName: "border-warning/40 bg-warning/10",
    textClassName: "text-warning",
  },
  unavailable: {
    Icon: TriangleAlert,
    get label() {
      return t("Unavailable");
    },
    surfaceClassName: "border-destructive/40 bg-destructive/10",
    textClassName: "text-destructive",
  },
};

const OVERALL_PRESENTATION: Record<ServiceState, { title: string }> = {
  online: {
    get title() {
      return t("All services operational");
    },
  },
  pending: {
    get title() {
      return t("Service checks in progress");
    },
  },
  unavailable: {
    get title() {
      return t("Attention required");
    },
  },
};

function overallServiceState(states: readonly ServiceState[]): ServiceState {
  if (states.includes("unavailable")) {
    return "unavailable";
  }
  if (states.includes("pending")) {
    return "pending";
  }
  return "online";
}

async function requestStatus(accessToken: string) {
  try {
    const result = await readSystemStatus({ auth: accessToken });
    return result.data ?? null;
  } catch {
    return null;
  }
}

export function ServiceStatus({
  accessToken,
  prominent = false,
}: ServiceStatusProps) {
  useUiLanguage();
  const [state, setState] = useState<StatusState>({ status: "loading" });
  const requestVersion = useRef(0);

  useEffect(() => {
    const version = requestVersion.current + 1;
    requestVersion.current = version;
    void requestStatus(accessToken).then((result) => {
      if (requestVersion.current === version) {
        setState(
          result === null
            ? { status: "error" }
            : { status: "loaded", data: result },
        );
      }
    });

    return () => {
      requestVersion.current += 1;
    };
  }, [accessToken]);

  if (state.status === "loading") {
    if (prominent) {
      return (
        <section
          aria-labelledby="service-status-title"
          className="grid gap-3 rounded-lg border-2 border-warning/40 bg-warning/10 p-6 shadow-sm"
          data-service-state="pending"
          data-testid="admin-service-status"
        >
          <div className="flex items-center gap-3 text-warning">
            <Clock3 aria-hidden="true" className="size-7" />
            <div className="grid gap-1">
              <p
                id="service-status-title"
                className="text-heading font-semibold"
              >
                {t("Service status")}
              </p>
              <p role="status" aria-live="polite" className="font-semibold">
                {t("Checking service status")}
              </p>
            </div>
          </div>
        </section>
      );
    }
    return <p role="status">{t("Checking service status")}</p>;
  }

  if (state.status === "error") {
    return (
      <Alert
        className={
          prominent
            ? "rounded-lg border-2 border-destructive/40 bg-destructive/10 p-6 shadow-sm"
            : "rounded-lg"
        }
        data-service-state={prominent ? "unavailable" : undefined}
        data-testid={prominent ? "admin-service-status" : undefined}
        variant={prominent ? "destructive" : "default"}
      >
        <AlertDescription>
          <div className="flex items-start gap-3">
            {prominent ? (
              <TriangleAlert aria-hidden="true" className="mt-0.5 size-7" />
            ) : null}
            <div className="grid gap-3">
              {prominent ? (
                <h2
                  id="service-status-title"
                  className="text-heading font-semibold"
                >
                  {t("Service status unavailable")}
                </h2>
              ) : null}
              <p>{t(API_ERROR_COPY)}</p>
            </div>
          </div>
          <Button
            type="button"
            variant="outline"
            className={prominent ? "mt-4" : undefined}
            onClick={() => {
              const version = requestVersion.current + 1;
              requestVersion.current = version;
              setState({ status: "loading" });
              void requestStatus(accessToken).then((result) => {
                if (requestVersion.current === version) {
                  setState(
                    result === null
                      ? { status: "error" }
                      : { status: "loaded", data: result },
                  );
                }
              });
            }}
          >
            {t("Retry connection")}
          </Button>
        </AlertDescription>
      </Alert>
    );
  }

  const status = state.data;
  const services = [
    ["API", status.api, Activity],
    [t("Database"), status.database, Database],
    ["Redis", status.redis, Layers3],
    [t("Worker"), status.worker, Cpu],
  ] as const;

  if (prominent) {
    const overallState = overallServiceState(
      services.map(([, serviceState]) => serviceState),
    );
    const overallStyle = STATE_PRESENTATION[overallState];
    const overallCopy = OVERALL_PRESENTATION[overallState];
    const OverallIcon = overallStyle.Icon;

    return (
      <section
        aria-labelledby="service-status-title"
        className={`grid gap-6 rounded-lg border-2 p-6 shadow-sm ${overallStyle.surfaceClassName}`}
        data-service-state={overallState}
        data-testid="admin-service-status"
      >
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="flex min-w-0 items-start gap-4">
            <span
              aria-hidden="true"
              className={`grid size-12 shrink-0 place-items-center rounded-full bg-secondary shadow-sm ${overallStyle.textClassName}`}
            >
              <OverallIcon className="size-7" />
            </span>
            <div className="grid gap-1">
              <h2
                id="service-status-title"
                className="text-label font-semibold tracking-wide text-muted-foreground uppercase"
              >
                {t("Service status")}
              </h2>
              <h3 className="text-heading font-semibold">
                {overallCopy.title}
              </h3>
            </div>
          </div>
          <Badge
            variant="outline"
            className={`rounded-md bg-secondary px-3 py-1 font-semibold ${overallStyle.textClassName}`}
          >
            <OverallIcon aria-hidden="true" />
            {overallStyle.label}
          </Badge>
        </div>

        <ul
          className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4"
          aria-label={t("Platform services")}
        >
          {services.map(([name, serviceState, ServiceIcon]) => {
            const serviceStyle = STATE_PRESENTATION[serviceState];
            const StatusIcon = serviceStyle.Icon;
            return (
              <li
                key={name}
                className={`grid gap-3 rounded-lg border bg-secondary p-4 shadow-sm ${serviceStyle.textClassName} ${serviceStyle.surfaceClassName.split(" ")[0]}`}
                data-service-state={serviceState}
              >
                <div className="flex items-center justify-between gap-3">
                  <ServiceIcon aria-hidden="true" className="size-6" />
                  <StatusIcon aria-hidden="true" className="size-5" />
                </div>
                <p className="font-semibold">
                  {name} {serviceState}
                </p>
              </li>
            );
          })}
        </ul>

        <p className="text-label text-muted-foreground">
          {t("Last checked:")}{" "}
          <time dateTime={status.checked_at}>{status.checked_at}</time>
        </p>
      </section>
    );
  }

  return (
    <section
      aria-labelledby="service-status-title"
      className="grid gap-4 border-y bg-secondary px-4 py-4"
    >
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 id="service-status-title" className="text-heading font-semibold">
          {t("Service status")}
        </h2>
        <p className="text-label text-muted-foreground">
          {t("Last checked:")}{" "}
          <time dateTime={status.checked_at}>{status.checked_at}</time>
        </p>
      </div>
      <ul className="flex flex-wrap gap-2" aria-label={t("Platform services")}>
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
