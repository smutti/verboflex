import { t, useUiLanguage } from "@/i18n";
import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useInRouterContext } from "react-router-dom";

import {
  getAdminBitbucketStatus,
  listAdminProducts,
  listAdminUsers,
  type AdminBitbucketStatusResponse,
  type CurrentUserResponse,
} from "../../api/client";
import { Alert, AlertDescription, AlertTitle } from "../../components/ui/alert";
import { Button } from "../../components/ui/button";
import { ServiceStatus } from "../../components/layout/ServiceStatus";
import { PersonalDashboard } from "./PersonalDashboard";

export interface WorkspaceOverviewPageProps {
  accessToken: string;
  principal: CurrentUserResponse;
}

interface AdminSummaries {
  bitbucketStatus: AdminBitbucketStatusResponse["status"];
  draftCount: number;
  inactiveCount: number;
  productCount: number;
  publishedCount: number;
  userCount: number;
}

type AdminLoadState =
  | { authorityKey: string; status: "loading" }
  | { authorityKey: string; status: "error" }
  | { authorityKey: string; status: "ready"; summaries: AdminSummaries };

function loadedCount(count: number, singular: string, plural = `${singular}s`) {
  return t(`{{count}} loaded ${count === 1 ? singular : plural}`, { count });
}

function countLabel(count: number, singular: string, plural = `${singular}s`) {
  return `${count} ${t(count === 1 ? singular : plural)}`;
}

function AdminDestinationLink({
  children,
  to,
}: {
  children: string;
  to: string;
}) {
  useUiLanguage();
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
  useUiLanguage();
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
          inactiveCount: productsResult.data.items.filter(
            (product) => !product.is_active,
          ).length,
          productCount: productsResult.data.items.length,
          publishedCount: productsResult.data.items.filter(
            (product) => product.active_revision !== null,
          ).length,
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
          {t("Project statistics")}
        </h2>
        <p role="status" aria-live="polite" className="text-muted-foreground">
          {t("Loading administrator summaries")}
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
          {t("Administrator summaries unavailable")}
        </AlertTitle>
        <AlertDescription className="grid gap-3">
          <Button
            type="button"
            variant="outline"
            className="w-fit"
            onClick={() => void loadSummaries()}
          >
            {t("Retry administrator summaries")}
          </Button>
        </AlertDescription>
      </Alert>
    );
  }

  const { summaries } = currentState;
  return (
    <section
      aria-labelledby="administrator-summaries-title"
      className="grid gap-5 rounded-lg border bg-secondary p-6"
    >
      <div className="grid gap-1">
        <h2
          id="administrator-summaries-title"
          className="text-heading font-semibold"
        >
          {t("Project statistics")}
        </h2>
        <p className="text-muted-foreground">
          {t("Counts include loaded items only.")}
        </p>
      </div>
      <dl className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        <div className="grid gap-2 rounded-lg border bg-background p-4 shadow-sm">
          <dt className="text-label font-semibold uppercase tracking-wide text-muted-foreground">
            {t("Configured products")}
          </dt>
          <dd className="text-heading font-semibold">
            {loadedCount(summaries.productCount, "product")}
          </dd>
          <AdminDestinationLink to="/admin/products">
            {t("Open Products")}
          </AdminDestinationLink>
        </div>
        <div className="grid gap-2 rounded-lg border bg-background p-4 shadow-sm">
          <dt className="text-label font-semibold uppercase tracking-wide text-muted-foreground">
            {t("Published products")}
          </dt>
          <dd className="text-heading font-semibold">
            {countLabel(summaries.publishedCount, "published product")}
          </dd>
          <AdminDestinationLink to="/admin/products">
            {t("View published products")}
          </AdminDestinationLink>
        </div>
        <div className="grid gap-2 rounded-lg border bg-background p-4 shadow-sm">
          <dt className="text-label font-semibold uppercase tracking-wide text-muted-foreground">
            {t("Draft configurations")}
          </dt>
          <dd className="text-heading font-semibold">
            {loadedCount(summaries.draftCount, "draft")}
          </dd>
          <AdminDestinationLink to="/admin/products">
            {t("Review drafts")}
          </AdminDestinationLink>
        </div>
        <div className="grid gap-2 rounded-lg border bg-background p-4 shadow-sm">
          <dt className="text-label font-semibold uppercase tracking-wide text-muted-foreground">
            {t("Inactive products")}
          </dt>
          <dd className="text-heading font-semibold">
            {countLabel(summaries.inactiveCount, "inactive product")}
          </dd>
          <AdminDestinationLink to="/admin/products">
            {t("Review inactive products")}
          </AdminDestinationLink>
        </div>
        <div className="grid gap-2 rounded-lg border bg-background p-4 shadow-sm">
          <dt className="text-label font-semibold uppercase tracking-wide text-muted-foreground">
            {t("Internal users")}
          </dt>
          <dd className="text-heading font-semibold">
            {loadedCount(summaries.userCount, "user")}
          </dd>
          <AdminDestinationLink to="/admin/users">
            {t("Open Users")}
          </AdminDestinationLink>
        </div>
        <div className="grid gap-2 rounded-lg border bg-background p-4 shadow-sm">
          <dt className="text-label font-semibold uppercase tracking-wide text-muted-foreground">
            {t("Bitbucket connection")}
          </dt>
          <dd className="text-heading font-semibold">
            {summaries.bitbucketStatus}
          </dd>
          <AdminDestinationLink to="/admin/bitbucket">
            {t("Open Bitbucket")}
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
  useUiLanguage();
  const isAdministrator = principal.roles.includes("admin");

  return (
    <div className="grid min-w-0 max-w-full gap-8">
      <section aria-labelledby="workspace-title" className="grid gap-2">
        <div className="grid gap-2">
          <h1
            id="workspace-title"
            tabIndex={-1}
            className="text-display font-semibold focus:outline-none"
          >
            {t("Dashboard")}
          </h1>
        </div>
      </section>

      <PersonalDashboard accessToken={accessToken} principal={principal} />

      {isAdministrator ? (
        <ServiceStatus accessToken={accessToken} prominent />
      ) : null}

      {!isAdministrator ? <ServiceStatus accessToken={accessToken} /> : null}

      {isAdministrator ? (
        <AdministratorSummaries
          accessToken={accessToken}
          principalId={principal.id}
        />
      ) : null}
    </div>
  );
}
