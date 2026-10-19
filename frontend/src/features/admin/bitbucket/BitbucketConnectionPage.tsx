import { t, useUiLanguage, getUiLanguage } from "@/i18n";
import { useCallback, useEffect, useRef, useState } from "react";

import {
  connectAdminBitbucketOauth,
  getAdminBitbucketStatus,
  reconnectAdminBitbucketOauth,
  revokeAdminBitbucketConnectionLocally,
  type AdminBitbucketCapabilityProfile,
  type AdminBitbucketStatusResponse,
} from "../../../api/client";
import {
  Alert,
  AlertDescription,
  AlertTitle,
} from "../../../components/ui/alert";
import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "../../../components/ui/alert-dialog";
import { Badge } from "../../../components/ui/badge";
import { Button } from "../../../components/ui/button";
import { Skeleton } from "../../../components/ui/skeleton";

import { BitbucketWorkspaceSettings } from "./BitbucketWorkspaceSettings";

export interface BitbucketConnectionPageProps {
  accessToken: string;
}

type LoadState =
  | { status: "loading" }
  | { status: "error" }
  | { status: "ready"; connection: AdminBitbucketStatusResponse };

type ConnectionAction = "connect" | "reconnect";
type CapabilityKey = "source_read" | "source_write" | "pull_request";
type CapabilityReadiness = AdminBitbucketCapabilityProfile[CapabilityKey];

const capabilityRows = [
  {
    key: "source_read",
    get label() {
      return t("Read localization sources");
    },
    supportingCopy: null,
  },
  {
    key: "source_write",
    get label() {
      return t("Create branches and source commits");
    },
    get supportingCopy() {
      return t("Not used during imports.");
    },
  },
  {
    key: "pull_request",
    get label() {
      return t("Open pull requests");
    },
    get supportingCopy() {
      return t("Not used during imports.");
    },
  },
] as const satisfies ReadonlyArray<{
  key: CapabilityKey;
  label: string;
  supportingCopy: string | null;
}>;

const capabilityReadinessLabels = {
  get disconnected() {
    return t("Disconnected");
  },
  get ready() {
    return t("Ready");
  },
  get ready_for_later_phase() {
    return t("Ready for a later phase");
  },
  get reauthorization_required() {
    return t("Reauthorization required");
  },
  get unavailable() {
    return t("Unavailable");
  },
} as const satisfies Record<CapabilityReadiness, string>;

function timestampFormatter() {
  return new Intl.DateTimeFormat(
    getUiLanguage() === "en" ? "en-GB" : getUiLanguage(),
    {
      day: "2-digit",
      hour: "2-digit",
      hour12: false,
      minute: "2-digit",
      month: "short",
      timeZone: "UTC",
      timeZoneName: "short",
      year: "numeric",
    },
  );
}

function boundedTimestamp(value: string | null) {
  if (value === null) {
    return null;
  }
  const timestamp = new Date(value);
  return Number.isNaN(timestamp.getTime())
    ? null
    : timestampFormatter().format(timestamp);
}

function ConnectionTimestamp({
  label,
  value,
}: {
  label: string;
  value: string | null;
}) {
  useUiLanguage();
  const bounded = boundedTimestamp(value);
  return bounded === null ? null : (
    <div>
      <dt className="text-muted-foreground">{label}</dt>
      <dd>
        <time dateTime={value ?? undefined}>{bounded}</time>
      </dd>
    </div>
  );
}

function CapabilityProfile({
  profile,
}: {
  profile: AdminBitbucketCapabilityProfile;
}) {
  useUiLanguage();
  return (
    <section aria-label={t("Capability profile")} className="grid gap-4">
      <h3 className="text-heading font-semibold">{t("Capability profile")}</h3>
      <dl className="grid divide-y">
        {capabilityRows.map((row) => (
          <div
            aria-label={row.label}
            className="grid min-w-0 gap-2 py-4 first:pt-0 last:pb-0 sm:grid-cols-[minmax(0,1fr)_minmax(12rem,auto)] sm:items-start sm:gap-6"
            key={row.key}
            role="group"
          >
            <dt className="font-medium">{row.label}</dt>
            <dd className="grid min-w-0 justify-items-start gap-1 sm:justify-items-end sm:text-right">
              <Badge
                variant="outline"
                className="h-auto max-w-full rounded-md whitespace-normal"
              >
                {capabilityReadinessLabels[profile[row.key]]}
              </Badge>
              {row.supportingCopy === null ? null : (
                <span className="text-muted-foreground">
                  {row.supportingCopy}
                </span>
              )}
            </dd>
          </div>
        ))}
      </dl>
    </section>
  );
}

function CapabilityProfileSkeleton() {
  useUiLanguage();
  return (
    <section aria-label={t("Capability profile")} className="grid gap-4">
      <h2 className="text-heading font-semibold">{t("Capability profile")}</h2>
      <dl className="grid divide-y">
        {capabilityRows.map((row) => (
          <div
            className="grid min-w-0 gap-2 py-4 first:pt-0 last:pb-0 sm:grid-cols-[minmax(0,1fr)_minmax(12rem,auto)] sm:items-center sm:gap-6"
            key={row.key}
          >
            <dt className="font-medium">{row.label}</dt>
            <dd className="sm:justify-self-end">
              <Skeleton
                aria-label={t("Loading capability readiness")}
                className="h-6 w-40 max-w-full"
              />
            </dd>
          </div>
        ))}
      </dl>
    </section>
  );
}

export function BitbucketConnectionPage({
  accessToken,
}: BitbucketConnectionPageProps) {
  useUiLanguage();
  const loadGenerationRef = useRef(0);
  const connectionPendingRef = useRef(false);
  const revokePendingRef = useRef(false);
  const revokeErrorRef = useRef<HTMLDivElement>(null);
  const revokeTriggerRef = useRef<HTMLButtonElement>(null);
  const [loadState, setLoadState] = useState<LoadState>({ status: "loading" });
  const [connectionPending, setConnectionPending] =
    useState<ConnectionAction | null>(null);
  const [connectionError, setConnectionError] = useState(false);
  const [connectionAnnouncement, setConnectionAnnouncement] = useState<
    string | null
  >(null);
  const [revokeOpen, setRevokeOpen] = useState(false);
  const [revokePending, setRevokePending] = useState(false);
  const [revokeError, setRevokeError] = useState(false);

  const loadConnection = useCallback(
    async (showLoading = true) => {
      const generation = ++loadGenerationRef.current;
      if (showLoading) {
        setLoadState({ status: "loading" });
      }
      try {
        const result = await getAdminBitbucketStatus({ auth: accessToken });
        if (generation !== loadGenerationRef.current) {
          return false;
        }
        if (result.data === undefined) {
          throw new Error();
        }
        setLoadState({ status: "ready", connection: result.data });
        return true;
      } catch {
        if (generation === loadGenerationRef.current && showLoading) {
          setLoadState({ status: "error" });
        }
        return false;
      }
    },
    [accessToken],
  );

  useEffect(() => {
    let active = true;
    queueMicrotask(() => {
      if (active) {
        void loadConnection();
      }
    });
    return () => {
      active = false;
      loadGenerationRef.current += 1;
    };
  }, [loadConnection]);

  useEffect(() => {
    if (revokeError) {
      revokeErrorRef.current?.focus();
    }
  }, [revokeError]);

  async function submitConnection(action: ConnectionAction) {
    if (connectionPendingRef.current) {
      return;
    }
    connectionPendingRef.current = true;
    setConnectionPending(action);
    setConnectionError(false);
    setConnectionAnnouncement(null);
    try {
      const result = await (action === "connect"
        ? connectAdminBitbucketOauth({ auth: accessToken })
        : reconnectAdminBitbucketOauth({ auth: accessToken }));
      if (result.data === undefined) {
        setConnectionError(true);
        return;
      }
      const refreshed = await loadConnection(false);
      if (!refreshed) {
        setConnectionError(true);
        return;
      }
      setConnectionAnnouncement(
        action === "connect" ? "Bitbucket connected" : "Bitbucket reconnected",
      );
    } catch {
      setConnectionError(true);
    } finally {
      connectionPendingRef.current = false;
      setConnectionPending(null);
    }
  }

  function changeRevokeOpen(open: boolean) {
    if (revokePendingRef.current) {
      return;
    }
    setRevokeOpen(open);
    if (!open) {
      setRevokeError(false);
      queueMicrotask(() => revokeTriggerRef.current?.focus());
    }
  }

  async function submitRevoke() {
    if (revokePendingRef.current) {
      return;
    }
    revokePendingRef.current = true;
    setRevokePending(true);
    setRevokeError(false);
    try {
      const result = await revokeAdminBitbucketConnectionLocally({
        auth: accessToken,
      });
      if (result.data === undefined) {
        setRevokeError(true);
        return;
      }
      setLoadState({ status: "ready", connection: result.data });
      setRevokeOpen(false);
    } catch {
      setRevokeError(true);
    } finally {
      revokePendingRef.current = false;
      setRevokePending(false);
    }
  }

  if (loadState.status === "loading") {
    return (
      <section className="grid min-w-0 max-w-3xl gap-8">
        <h1 className="text-display font-semibold">Bitbucket</h1>
        <div className="grid gap-6" role="status" aria-live="polite">
          <section
            aria-label={t("Bitbucket connection status")}
            className="grid gap-5 rounded-lg border bg-secondary p-6"
          >
            <div className="flex flex-wrap items-center justify-between gap-4">
              <h2 className="text-heading font-semibold">
                {t("Connection status")}
              </h2>
              <Skeleton className="h-6 w-28 max-w-full" />
            </div>
            <CapabilityProfileSkeleton />
          </section>
          <span className="sr-only">{t("Loading Bitbucket connection")}</span>
        </div>
      </section>
    );
  }

  if (loadState.status === "error") {
    return (
      <section className="grid max-w-3xl gap-6">
        <h1 className="text-display font-semibold">Bitbucket</h1>
        <Alert variant="destructive">
          <AlertTitle>{t("Bitbucket connection unavailable")}</AlertTitle>
          <AlertDescription>
            <Button
              type="button"
              variant="outline"
              onClick={() => void loadConnection()}
            >
              {t("Retry loading page")}
            </Button>
          </AlertDescription>
        </Alert>
      </section>
    );
  }

  const connection = loadState.connection;
  const hasBoundedTimestamp = [
    connection.connected_at,
    connection.expires_at,
    connection.revoked_at,
  ].some((value) => boundedTimestamp(value) !== null);
  const reconnect =
    connection.status === "Reauthorization required" ||
    connection.status === "Unavailable";
  const hasExpandedCapabilityProfile =
    connection.scope_label === "Repository and pull-request access" &&
    connection.scope_profile === "repository_and_pull_request";

  return (
    <section className="grid min-w-0 max-w-3xl gap-8">
      <div className="grid gap-2">
        <h1 className="text-display font-semibold">Bitbucket</h1>
        <p className="text-muted-foreground">
          {t("Shared connection for all products.")}
        </p>
      </div>

      <BitbucketWorkspaceSettings accessToken={accessToken} />

      {connectionError ? (
        <Alert variant="destructive">
          <AlertTitle>{t("Bitbucket connection unavailable")}</AlertTitle>
          <AlertDescription>
            {t(
              "Verify the server configuration, then try again. The current connection status is unchanged.",
            )}
          </AlertDescription>
        </Alert>
      ) : null}

      {connectionPending !== null || connectionAnnouncement !== null ? (
        <div
          role="status"
          aria-label={t("Bitbucket connection mutation")}
          aria-live="polite"
        >
          {connectionPending === "connect"
            ? t("Connecting Bitbucket")
            : connectionPending === "reconnect"
              ? t("Reconnecting Bitbucket")
              : connectionAnnouncement}
        </div>
      ) : null}

      <section
        aria-label={t("Bitbucket connection status")}
        className="grid gap-5 rounded-lg border bg-secondary p-6"
      >
        <div className="flex flex-wrap items-center justify-between gap-4">
          <h2 className="text-heading font-semibold">
            {t("Connection status")}
          </h2>
          <Badge variant="outline" className="w-fit rounded-md">
            {t(connection.status)}
          </Badge>
        </div>

        {hasExpandedCapabilityProfile ? (
          <p className="font-medium">
            {t("Repository and pull-request access")}
          </p>
        ) : null}

        {hasBoundedTimestamp ? (
          <dl className="grid gap-3 sm:grid-cols-2">
            <ConnectionTimestamp
              label={t("Connected")}
              value={connection.connected_at}
            />
            <ConnectionTimestamp
              label={t("Access expires")}
              value={connection.expires_at}
            />
            <ConnectionTimestamp
              label={t("Revoked")}
              value={connection.revoked_at}
            />
          </dl>
        ) : null}

        <CapabilityProfile profile={connection.capability_profile} />

        <div className="flex flex-wrap gap-3">
          {connection.status === "Disconnected" ? (
            <Button
              type="button"
              disabled={connectionPending === "connect"}
              aria-busy={connectionPending === "connect"}
              onClick={() => void submitConnection("connect")}
            >
              {t("Connect Bitbucket")}
            </Button>
          ) : null}
          {reconnect ? (
            <Button
              type="button"
              disabled={connectionPending === "reconnect"}
              aria-busy={connectionPending === "reconnect"}
              onClick={() => void submitConnection("reconnect")}
            >
              {t("Reconnect Bitbucket")}
            </Button>
          ) : null}
          {connection.status !== "Disconnected" ? (
            <Button
              ref={revokeTriggerRef}
              type="button"
              variant="destructive"
              onClick={() => setRevokeOpen(true)}
            >
              {t("Revoke connection")}
            </Button>
          ) : null}
        </div>
      </section>

      {revokeOpen ? (
        <AlertDialog open onOpenChange={changeRevokeOpen}>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>
                {t("Revoke the Bitbucket connection?")}
              </AlertDialogTitle>
              <AlertDialogDescription>
                {t(
                  "New imports, branch reads, previews, confirmations, and publications will be blocked until an administrator reconnects. Existing successful baselines remain recorded.",
                )}
              </AlertDialogDescription>
            </AlertDialogHeader>

            {revokeError ? (
              <Alert ref={revokeErrorRef} tabIndex={-1} variant="destructive">
                <AlertTitle>{t("Connection not revoked")}</AlertTitle>
                <AlertDescription>
                  {t(
                    "The current Bitbucket connection remains unchanged. Try again.",
                  )}
                </AlertDescription>
              </Alert>
            ) : null}

            <AlertDialogFooter>
              <AlertDialogCancel disabled={revokePending}>
                {t("Cancel")}
              </AlertDialogCancel>
              <Button
                type="button"
                variant="destructive"
                disabled={revokePending}
                aria-busy={revokePending}
                onClick={() => void submitRevoke()}
              >
                {t("Revoke connection")}
              </Button>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      ) : null}
    </section>
  );
}
