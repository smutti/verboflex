import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useInRouterContext } from "react-router-dom";

import {
  getAdminBitbucketStatus,
  listAdminProducts,
  listAdminUsers,
  type AdminBitbucketStatusResponse,
  type CurrentUserResponse,
  type RoleName,
} from "../../api/client";
import { Alert, AlertDescription, AlertTitle } from "../../components/ui/alert";
import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { ServiceStatus } from "../../components/layout/ServiceStatus";

export interface WorkspaceOverviewPageProps {
  accessToken: string;
  principal: CurrentUserResponse;
}

const ROLE_LABELS: Record<RoleName, string> = {
  admin: "Administrator",
  product_manager_reviewer: "Product manager / reviewer",
  translator: "Translator",
  viewer: "Viewer",
};

interface AdminSummaries {
  bitbucketStatus: AdminBitbucketStatusResponse["status"];
  draftCount: number;
  productCount: number;
  userCount: number;
}

type AdminLoadState =
  | { authorityKey: string; status: "loading" }
  | { authorityKey: string; status: "error" }
  | { authorityKey: string; status: "ready"; summaries: AdminSummaries };

function loadedCount(count: number, singular: string, plural = `${singular}s`) {
  return `${count} loaded ${count === 1 ? singular : plural}`;
}

function AdminDestinationLink({
  children,
  to,
}: {
  children: string;
  to: string;
}) {
  const isWithinRouter = useInRouterContext();
  const className =
    "font-semibold text-primary underline-offset-4 hover:underline focus-visible:underline";

  return isWithinRouter ? (
    <Link className={className} to={to}>
      {children}
    </Link>
  ) : (
    <a className={className} href={to}>
      {children}
    </a>
  );
}

function AdministratorSummaries({
  accessToken,
  principalId,
}: {
  accessToken: string;
  principalId: string;
}) {
  const requestGeneration = useRef(0);
  const authorityKey = `${principalId}:${accessToken}`;
  const [loadState, setLoadState] = useState<AdminLoadState>({
    authorityKey,
    status: "loading",
  });

  const loadSummaries = useCallback(async () => {
    const generation = ++requestGeneration.current;
    setLoadState({ authorityKey, status: "loading" });

    try {
      const [productsResult, usersResult, bitbucketResult] = await Promise.all([
        listAdminProducts({
          auth: accessToken,
          query: { cursor: null, limit: 50, status: null },
        }),
        listAdminUsers({
          auth: accessToken,
          query: { cursor: null, limit: 50 },
        }),
        getAdminBitbucketStatus({ auth: accessToken }),
      ]);
      if (generation !== requestGeneration.current) {
        return;
      }
      if (
        productsResult.data === undefined ||
        usersResult.data === undefined ||
        bitbucketResult.data === undefined
      ) {
        throw new Error("Administrator summary request rejected");
      }
      setLoadState({
        authorityKey,
        status: "ready",
        summaries: {
          bitbucketStatus: bitbucketResult.data.status,
          draftCount: productsResult.data.items.filter(
            (product) => product.candidate_revision !== null,
          ).length,
          productCount: productsResult.data.items.length,
          userCount: usersResult.data.items.length,
        },
      });
    } catch {
      if (generation === requestGeneration.current) {
        setLoadState({ authorityKey, status: "error" });
      }
    }
  }, [accessToken, authorityKey]);

  useEffect(() => {
    let active = true;
    queueMicrotask(() => {
      if (active) {
        void loadSummaries();
      }
    });
    return () => {
      active = false;
      requestGeneration.current += 1;
    };
  }, [loadSummaries]);

  const currentState: AdminLoadState =
    loadState.authorityKey === authorityKey
      ? loadState
      : { authorityKey, status: "loading" };

  if (currentState.status === "loading") {
    return (
      <section
        aria-labelledby="administrator-summaries-title"
        className="grid gap-3 rounded-lg border bg-secondary p-6"
      >
        <h2
          id="administrator-summaries-title"
          className="text-heading font-semibold"
        >
          Administration summary
        </h2>
        <p role="status" aria-live="polite" className="text-muted-foreground">
          Loading administrator summaries
        </p>
      </section>
    );
  }

  if (currentState.status === "error") {
    return (
      <Alert
        variant="destructive"
        role="alert"
        aria-labelledby="administrator-summaries-error-title"
      >
        <AlertTitle id="administrator-summaries-error-title">
          Administrator summaries unavailable
        </AlertTitle>
        <AlertDescription className="grid gap-3">
          <p>
            We could not load administrator summaries. Your identity and service
            status remain available.
          </p>
          <Button
            type="button"
            variant="outline"
            className="w-fit"
            onClick={() => void loadSummaries()}
          >
            Retry administrator summaries
          </Button>
        </AlertDescription>
      </Alert>
    );
  }

  const { summaries } = currentState;
  return (
    <section
      aria-labelledby="administrator-summaries-title"
      className="grid gap-4 rounded-lg border bg-secondary p-6"
    >
      <div className="grid gap-1">
        <h2
          id="administrator-summaries-title"
          className="text-heading font-semibold"
        >
          Administration summary
        </h2>
        <p className="text-muted-foreground">
          Loaded summaries cover the first bounded page.
        </p>
      </div>
      <dl className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <div className="grid gap-1">
          <dt className="text-muted-foreground">Products</dt>
          <dd className="font-semibold">
            {loadedCount(summaries.productCount, "product")}
          </dd>
          <AdminDestinationLink to="/admin/products">
            Open Products
          </AdminDestinationLink>
        </div>
        <div className="grid gap-1">
          <dt className="text-muted-foreground">Draft configurations</dt>
          <dd className="font-semibold">
            {loadedCount(summaries.draftCount, "draft")}
          </dd>
          <AdminDestinationLink to="/admin/products">
            Review drafts
          </AdminDestinationLink>
        </div>
        <div className="grid gap-1">
          <dt className="text-muted-foreground">Internal users</dt>
          <dd className="font-semibold">
            {loadedCount(summaries.userCount, "user")}
          </dd>
          <AdminDestinationLink to="/admin/users">
            Open Users
          </AdminDestinationLink>
        </div>
        <div className="grid gap-1">
          <dt className="text-muted-foreground">Bitbucket connection</dt>
          <dd className="font-semibold">{summaries.bitbucketStatus}</dd>
          <AdminDestinationLink to="/admin/bitbucket">
            Open Bitbucket
          </AdminDestinationLink>
        </div>
      </dl>
    </section>
  );
}

export function WorkspaceOverviewPage({
  accessToken,
  principal,
}: WorkspaceOverviewPageProps) {
  const isAdministrator = principal.roles.includes("admin");

  return (
    <div className="grid min-w-0 max-w-full gap-8">
      <section aria-labelledby="workspace-title" className="grid gap-4">
        <div className="grid gap-2">
          <h1
            id="workspace-title"
            tabIndex={-1}
            className="text-display font-semibold focus:outline-none"
          >
            Workspace
          </h1>
          <p className="max-w-3xl text-muted-foreground">
            Review your authenticated identity and the current VerboFlex service
            status.
          </p>
        </div>
        <div className="grid gap-2 rounded-lg border bg-secondary p-6">
          <h2 className="text-heading font-semibold">Signed-in identity</h2>
          <p className="font-semibold">{principal.display_name}</p>
          <p className="break-words text-muted-foreground [overflow-wrap:anywhere]">
            {principal.email}
          </p>
          <div className="flex flex-wrap gap-2" aria-label="Assigned roles">
            {principal.roles.map((role) => (
              <Badge key={role} variant="outline" className="rounded-md">
                {ROLE_LABELS[role]}
              </Badge>
            ))}
          </div>
        </div>
      </section>

      <ServiceStatus accessToken={accessToken} />

      {isAdministrator ? (
        <AdministratorSummaries
          accessToken={accessToken}
          principalId={principal.id}
        />
      ) : (
        <section
          aria-labelledby="workspace-access-title"
          className="grid gap-2 rounded-lg border bg-secondary p-6"
        >
          <h2
            id="workspace-access-title"
            className="text-heading font-semibold"
          >
            Workspace access
          </h2>
          <p className="max-w-3xl text-muted-foreground">
            No administrator summaries are available for your role. Your
            authorized translation work will appear here as products are made
            available.
          </p>
        </section>
      )}
    </div>
  );
}
