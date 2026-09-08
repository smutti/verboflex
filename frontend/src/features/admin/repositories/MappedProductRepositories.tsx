import { useCallback, useEffect, useRef, useState } from "react";
import { FolderGit2, GitBranch, Network } from "lucide-react";
import { Link } from "react-router-dom";

import {
  getAdminProduct,
  listAdminRepositories,
  type AdminRepositoryListResponse,
  type AdminRepositoryResponse,
} from "../../../api/client";
import {
  Alert,
  AlertDescription,
  AlertTitle,
} from "../../../components/ui/alert";
import { Badge } from "../../../components/ui/badge";
import { Button } from "../../../components/ui/button";
import { Skeleton } from "../../../components/ui/skeleton";
import { loadMappedRepositoryIds } from "./product-repository-usage";

const REPOSITORY_PAGE_SIZE = 50;
const MAX_REPOSITORY_PAGES = 50;

type LoadState =
  | { status: "loading" }
  | { status: "error" }
  | { status: "ready"; repositories: AdminRepositoryResponse[] };

function repositoryLabel(repository: AdminRepositoryResponse) {
  return (
    repository.descriptive_name ??
    `${repository.workspace}/${repository.repository_slug}`
  );
}

async function loadProductRepositories({
  accessToken,
  productId,
  signal,
}: {
  accessToken: string;
  productId: string;
  signal: AbortSignal;
}) {
  const productResult = await getAdminProduct({
    auth: accessToken,
    path: { product_id: productId },
    signal,
  });
  if (signal.aborted) {
    throw new DOMException("The operation was aborted", "AbortError");
  }
  if (productResult.data === undefined) {
    throw new Error("product unavailable");
  }

  const revision =
    productResult.data.candidate_revision ?? productResult.data.active_revision;
  if (revision === null) {
    return [];
  }

  const repositoryIds = await loadMappedRepositoryIds({
    accessToken,
    productId,
    revisionId: revision.id,
    signal,
  });
  if (repositoryIds.length === 0) {
    return [];
  }

  const wantedIds = new Set(repositoryIds);
  const repositoriesById = new Map<string, AdminRepositoryResponse>();
  const consumedCursors = new Set<string>();
  let cursor: string | null = null;
  let pageCount = 0;

  do {
    if (signal.aborted) {
      throw new DOMException("The operation was aborted", "AbortError");
    }
    if (pageCount >= MAX_REPOSITORY_PAGES) {
      throw new Error("repository catalogue exceeded page limit");
    }
    const result: { data?: AdminRepositoryListResponse } =
      await listAdminRepositories({
        auth: accessToken,
        query: { cursor, limit: REPOSITORY_PAGE_SIZE },
        signal,
      });
    if (signal.aborted) {
      throw new DOMException("The operation was aborted", "AbortError");
    }
    if (result.data === undefined) {
      throw new Error("repository catalogue unavailable");
    }
    for (const repository of result.data.items) {
      if (wantedIds.has(repository.id)) {
        repositoriesById.set(repository.id, repository);
      }
    }
    cursor = result.data.next_cursor;
    pageCount += 1;
    if (repositoriesById.size === wantedIds.size) {
      break;
    }
    if (cursor !== null) {
      if (consumedCursors.has(cursor)) {
        throw new Error("repository catalogue repeated cursor");
      }
      consumedCursors.add(cursor);
    }
  } while (cursor !== null);

  if (repositoriesById.size !== wantedIds.size) {
    throw new Error("mapped repository unavailable");
  }
  return repositoryIds.map((repositoryId) =>
    repositoriesById.get(repositoryId)!,
  );
}

export function MappedProductRepositories({
  accessToken,
  productId,
}: {
  accessToken: string;
  productId: string;
}) {
  const generationRef = useRef(0);
  const controllerRef = useRef<AbortController | null>(null);
  const errorRef = useRef<HTMLDivElement>(null);
  const [loadState, setLoadState] = useState<LoadState>({
    status: "loading",
  });

  const load = useCallback(async () => {
    const generation = ++generationRef.current;
    controllerRef.current?.abort();
    const controller = new AbortController();
    controllerRef.current = controller;
    setLoadState({ status: "loading" });
    try {
      const repositories = await loadProductRepositories({
        accessToken,
        productId,
        signal: controller.signal,
      });
      if (!controller.signal.aborted && generation === generationRef.current) {
        setLoadState({ status: "ready", repositories });
      }
    } catch {
      if (!controller.signal.aborted && generation === generationRef.current) {
        setLoadState({ status: "error" });
      }
    }
  }, [accessToken, productId]);

  useEffect(() => {
    queueMicrotask(() => void load());
    return () => {
      generationRef.current += 1;
      controllerRef.current?.abort();
    };
  }, [load]);

  useEffect(() => {
    if (loadState.status === "error") {
      errorRef.current!.focus();
    }
  }, [loadState.status]);

  const mappingsUrl = `/admin/products/${encodeURIComponent(productId)}/mappings`;

  return (
    <section
      className="grid min-w-0 max-w-full gap-8 overflow-x-clip"
      aria-labelledby="product-repositories-title"
      aria-busy={loadState.status === "loading"}
    >
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div className="grid min-w-0 gap-2">
          <h1
            id="product-repositories-title"
            className="text-display font-semibold"
          >
            Repositories used by this product
          </h1>
          <p className="max-w-3xl text-muted-foreground">
            This list comes directly from saved mappings. Global repository
            registration does not associate a repository with this product.
          </p>
        </div>
        {loadState.status === "ready" && loadState.repositories.length > 0 ? (
          <Badge variant="success" className="rounded-md px-3 py-1">
            {loadState.repositories.length}{" "}
            {loadState.repositories.length === 1
              ? "repository in use"
              : "repositories in use"}
          </Badge>
        ) : null}
      </header>

      {loadState.status === "loading" ? (
        <section
          className="grid gap-3"
          role="status"
          aria-live="polite"
          aria-label="Loading product repositories"
        >
          <Skeleton className="h-28 w-full rounded-xl" />
          <Skeleton className="h-28 w-full rounded-xl" />
          <span className="text-sm text-muted-foreground">
            Resolving repositories from saved mappings
          </span>
        </section>
      ) : null}

      {loadState.status === "error" ? (
        <Alert ref={errorRef} tabIndex={-1} variant="destructive">
          <AlertTitle>Product repositories unavailable</AlertTitle>
          <AlertDescription>
            <p>
              We could not resolve the repositories used by the current product
              mappings. No global repository is shown as associated.
            </p>
            <Button type="button" variant="outline" onClick={() => void load()}>
              Retry loading product repositories
            </Button>
          </AlertDescription>
        </Alert>
      ) : null}

      {loadState.status === "ready" && loadState.repositories.length === 0 ? (
        <section className="grid min-h-[38vh] place-items-center rounded-xl border border-dashed bg-secondary/40 p-8 text-center">
          <div className="grid max-w-lg justify-items-center gap-4">
            <span className="bg-background text-muted-foreground grid size-16 place-items-center rounded-full border shadow-sm">
              <FolderGit2
                data-testid="product-repositories-empty-icon"
                aria-hidden="true"
                className="size-8"
              />
            </span>
            <div className="grid gap-2">
              <h2 className="text-heading font-semibold">
                No repositories in use
              </h2>
              <p className="text-muted-foreground">
                Save a mapping to associate its repository and branch with this
                product.
              </p>
            </div>
            <Button asChild>
              <Link to={mappingsUrl}>Configure a mapping</Link>
            </Button>
          </div>
        </section>
      ) : null}

      {loadState.status === "ready" && loadState.repositories.length > 0 ? (
        <>
          <ul
            className="grid list-none gap-4 p-0 lg:grid-cols-2"
            aria-label="Repositories used by this product"
          >
            {loadState.repositories.map((repository) => (
              <li key={repository.id} className="min-w-0">
                <article className="grid h-full min-w-0 gap-4 rounded-xl border bg-card p-6 shadow-sm">
                  <div className="flex min-w-0 items-start gap-3">
                    <span className="bg-success/10 text-success grid size-11 shrink-0 place-items-center rounded-lg">
                      <Network aria-hidden="true" className="size-5" />
                    </span>
                    <div className="grid min-w-0 gap-1">
                      <h2 className="break-words text-heading font-semibold [overflow-wrap:anywhere]">
                        {repositoryLabel(repository)}
                      </h2>
                      <span className="flex min-w-0 items-center gap-2 text-sm text-muted-foreground">
                        <GitBranch
                          aria-hidden="true"
                          className="size-4 shrink-0"
                        />
                        <code className="break-all">
                          {repository.workspace}/{repository.repository_slug}
                        </code>
                      </span>
                    </div>
                  </div>
                  <Badge variant="success" className="rounded-md">
                    Connected by a saved mapping
                  </Badge>
                </article>
              </li>
            ))}
          </ul>
          <aside
            role="note"
            className="flex flex-wrap items-center justify-between gap-4 rounded-xl border bg-secondary/50 p-5"
          >
            <p className="max-w-2xl text-sm text-muted-foreground">
              Branches, localization roots, and pull-request targets are
              configured in each mapping.
            </p>
            <Button asChild variant="outline">
              <Link to={mappingsUrl}>Manage mappings</Link>
            </Button>
          </aside>
        </>
      ) : null}
    </section>
  );
}
