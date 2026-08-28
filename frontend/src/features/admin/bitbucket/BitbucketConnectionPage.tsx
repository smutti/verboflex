import { useCallback, useEffect, useRef, useState } from "react";

import {
  getAdminBitbucketStatus,
  reconnectAdminBitbucketOauth,
  revokeAdminBitbucketConnectionLocally,
  startAdminBitbucketOauth,
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

export interface BitbucketConnectionPageProps {
  accessToken: string;
  navigateTo?: (url: string) => void;
}

type LoadState =
  | { status: "loading" }
  | { status: "error" }
  | { status: "ready"; connection: AdminBitbucketStatusResponse };

type AuthorizationAction = "connect" | "reconnect";

const timestampFormatter = new Intl.DateTimeFormat("en-GB", {
  day: "2-digit",
  hour: "2-digit",
  hour12: false,
  minute: "2-digit",
  month: "short",
  timeZone: "UTC",
  timeZoneName: "short",
  year: "numeric",
});

function boundedTimestamp(value: string | null) {
  if (value === null) {
    return null;
  }
  const timestamp = new Date(value);
  return Number.isNaN(timestamp.getTime())
    ? null
    : timestampFormatter.format(timestamp);
}

function defaultNavigateTo(url: string) {
  window.location.assign(url);
}

function safeAuthorizationDestination(value: string) {
  try {
    const destination = new URL(value);
    return destination.protocol === "https:" &&
      destination.username === "" &&
      destination.password === "" &&
      destination.hash === ""
      ? destination.href
      : null;
  } catch {
    return null;
  }
}

function ConnectionTimestamp({
  label,
  value,
}: {
  label: string;
  value: string | null;
}) {
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

export function BitbucketConnectionPage({
  accessToken,
  navigateTo = defaultNavigateTo,
}: BitbucketConnectionPageProps) {
  const loadGenerationRef = useRef(0);
  const authorizationPendingRef = useRef(false);
  const revokePendingRef = useRef(false);
  const revokeErrorRef = useRef<HTMLDivElement>(null);
  const revokeTriggerRef = useRef<HTMLButtonElement>(null);
  const [loadState, setLoadState] = useState<LoadState>({ status: "loading" });
  const [authorizationPending, setAuthorizationPending] =
    useState<AuthorizationAction | null>(null);
  const [authorizationError, setAuthorizationError] = useState(false);
  const [revokeOpen, setRevokeOpen] = useState(false);
  const [revokePending, setRevokePending] = useState(false);
  const [revokeError, setRevokeError] = useState(false);

  const loadConnection = useCallback(async () => {
    const generation = ++loadGenerationRef.current;
    setLoadState({ status: "loading" });
    try {
      const result = await getAdminBitbucketStatus({ auth: accessToken });
      if (generation !== loadGenerationRef.current) {
        return;
      }
      if (result.data === undefined) {
        throw new Error();
      }
      setLoadState({ status: "ready", connection: result.data });
    } catch {
      if (generation === loadGenerationRef.current) {
        setLoadState({ status: "error" });
      }
    }
  }, [accessToken]);

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

  async function beginAuthorization(action: AuthorizationAction) {
    if (authorizationPendingRef.current) {
      return;
    }
    authorizationPendingRef.current = true;
    setAuthorizationPending(action);
    setAuthorizationError(false);
    try {
      const result = await (action === "connect"
        ? startAdminBitbucketOauth({ auth: accessToken })
        : reconnectAdminBitbucketOauth({ auth: accessToken }));
      const destination =
        result.data === undefined
          ? null
          : safeAuthorizationDestination(result.data.authorization_url);
      if (destination === null) {
        setAuthorizationError(true);
        return;
      }
      navigateTo(destination);
    } catch {
      setAuthorizationError(true);
    } finally {
      authorizationPendingRef.current = false;
      setAuthorizationPending(null);
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
      <section className="grid max-w-3xl gap-6">
        <h1 className="text-display font-semibold">Bitbucket</h1>
        <div className="grid gap-4" role="status" aria-live="polite">
          <Skeleton className="h-8 w-48 max-w-full" />
          <Skeleton className="h-40 w-full" />
          <span>Loading Bitbucket connection</span>
        </div>
      </section>
    );
  }

  if (loadState.status === "error") {
    return (
      <section className="grid max-w-3xl gap-6">
        <h1 className="text-display font-semibold">Bitbucket</h1>
        <Alert variant="destructive">
          <AlertTitle>Bitbucket connection unavailable</AlertTitle>
          <AlertDescription>
            <p>
              We could not load this page. Retry without leaving the
              administration area.
            </p>
            <Button
              type="button"
              variant="outline"
              onClick={() => void loadConnection()}
            >
              Retry loading page
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

  return (
    <section className="grid min-w-0 max-w-3xl gap-8">
      <div className="grid gap-2">
        <h1 className="text-display font-semibold">Bitbucket</h1>
        <p className="text-muted-foreground">
          Manage the organization-wide connection used for localization source
          discovery.
        </p>
      </div>

      {authorizationError ? (
        <Alert variant="destructive">
          <AlertTitle>Connection could not start</AlertTitle>
          <AlertDescription>
            Bitbucket connection unavailable. Try again without leaving this
            page.
          </AlertDescription>
        </Alert>
      ) : null}

      <section
        aria-label="Bitbucket connection status"
        className="grid gap-5 rounded-lg border bg-secondary p-6"
      >
        <div className="flex flex-wrap items-center justify-between gap-4">
          <h2 className="text-heading font-semibold">Connection status</h2>
          <Badge variant="outline" className="w-fit rounded-md">
            {connection.status}
          </Badge>
        </div>

        <p className="font-medium">Read-only repository access</p>

        {hasBoundedTimestamp ? (
          <dl className="grid gap-3 sm:grid-cols-2">
            <ConnectionTimestamp
              label="Connected"
              value={connection.connected_at}
            />
            <ConnectionTimestamp
              label="Access expires"
              value={connection.expires_at}
            />
            <ConnectionTimestamp label="Revoked" value={connection.revoked_at} />
          </dl>
        ) : null}

        <div className="flex flex-wrap gap-3">
          {connection.status === "Disconnected" ? (
            <Button
              type="button"
              disabled={authorizationPending !== null}
              aria-busy={authorizationPending === "connect"}
              onClick={() => void beginAuthorization("connect")}
            >
              Connect Bitbucket
            </Button>
          ) : null}
          {reconnect ? (
            <Button
              type="button"
              disabled={authorizationPending !== null}
              aria-busy={authorizationPending === "reconnect"}
              onClick={() => void beginAuthorization("reconnect")}
            >
              Reconnect Bitbucket
            </Button>
          ) : null}
          {connection.status !== "Disconnected" ? (
            <Button
              ref={revokeTriggerRef}
              type="button"
              variant="destructive"
              disabled={authorizationPending !== null}
              onClick={() => setRevokeOpen(true)}
            >
              Revoke connection
            </Button>
          ) : null}
        </div>
      </section>

      {revokeOpen ? (
        <AlertDialog open onOpenChange={changeRevokeOpen}>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>
                Revoke the Bitbucket connection?
              </AlertDialogTitle>
              <AlertDialogDescription>
                New branch reads, previews, confirmations, and publications
                will be blocked until an administrator reconnects.
              </AlertDialogDescription>
            </AlertDialogHeader>

            {revokeError ? (
              <Alert
                ref={revokeErrorRef}
                tabIndex={-1}
                variant="destructive"
              >
                <AlertTitle>Connection not revoked</AlertTitle>
                <AlertDescription>
                  The current Bitbucket connection remains unchanged. Try
                  again.
                </AlertDescription>
              </Alert>
            ) : null}

            <AlertDialogFooter>
              <AlertDialogCancel disabled={revokePending}>
                Cancel
              </AlertDialogCancel>
              <Button
                type="button"
                variant="destructive"
                disabled={revokePending}
                aria-busy={revokePending}
                onClick={() => void submitRevoke()}
              >
                Revoke connection
              </Button>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      ) : null}
    </section>
  );
}
