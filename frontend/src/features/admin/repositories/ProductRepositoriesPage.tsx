import { t, useUiLanguage } from "@/i18n";
import { useCallback, useEffect, useId, useRef, useState } from "react";
import { Link } from "react-router-dom";

import {
  getAdminBitbucketWorkspace,
  getAdminRepository,
  listAdminBitbucketRepositories,
  selectAdminBitbucketRepository,
  type AdminBitbucketRepositoryResponse,
  type AdminRepositoryResponse,
} from "../../../api/client";
import {
  Alert,
  AlertDescription,
  AlertTitle,
} from "../../../components/ui/alert";
import { Badge } from "../../../components/ui/badge";
import { Button } from "../../../components/ui/button";
import { Input } from "../../../components/ui/input";
import { Label } from "../../../components/ui/label";
import { Skeleton } from "../../../components/ui/skeleton";
import { useCursorCollection } from "../useCursorCollection";
import { MappedProductRepositories } from "./MappedProductRepositories";
import { GitHubRepositoryPicker } from "./GitHubRepositoryPicker";

export interface ProductRepositoriesPageProps {
  accessToken: string;
  embedded?: boolean;
  onRepositorySelected?: (repository: AdminRepositoryResponse) => void;
  productId?: string;
  selectedRepositoryIds?: readonly string[];
}

export function ProductRepositoriesPage(props: ProductRepositoriesPageProps) {
  useUiLanguage();
  return props.productId !== undefined ? (
    <MappedProductRepositories
      accessToken={props.accessToken}
      productId={props.productId}
    />
  ) : (
    <RepositoryProviderPicker {...props} />
  );
}

function RepositoryProviderPicker(
  props: Omit<ProductRepositoriesPageProps, "productId">,
) {
  useUiLanguage();
  const [provider, setProvider] = useState<"bitbucket" | "github">("bitbucket");
  return (
    <div className="grid gap-6">
      <div
        className="flex gap-2"
        role="group"
        aria-label={t("Repository provider")}
      >
        <Button
          type="button"
          variant={provider === "bitbucket" ? "default" : "outline"}
          aria-pressed={provider === "bitbucket"}
          onClick={() => setProvider("bitbucket")}
        >
          Bitbucket Cloud
        </Button>
        <Button
          type="button"
          variant={provider === "github" ? "default" : "outline"}
          aria-pressed={provider === "github"}
          onClick={() => setProvider("github")}
        >
          GitHub
        </Button>
      </div>
      {provider === "github" ? (
        <GitHubRepositoryPicker
          accessToken={props.accessToken}
          onRepositorySelected={props.onRepositorySelected}
          selectedRepositoryIds={props.selectedRepositoryIds}
        />
      ) : (
        <BitbucketRepositoryPicker {...props} />
      )}
    </div>
  );
}

function BitbucketRepositoryPicker({
  accessToken,
  embedded = false,
  onRepositorySelected,
  selectedRepositoryIds = [],
}: Omit<ProductRepositoriesPageProps, "productId">) {
  useUiLanguage();
  const searchId = useId();
  const [workspace, setWorkspace] = useState<string | null>();
  const [workspaceError, setWorkspaceError] = useState(false);
  const [reload, setReload] = useState(0);
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");
  const [pending, setPending] = useState<string | null>(null);
  const pendingRef = useRef(false);
  const [selectionError, setSelectionError] = useState(false);
  const [selected, setSelected] = useState<AdminRepositoryResponse[]>([]);
  const selectedKey = JSON.stringify(selectedRepositoryIds);

  useEffect(() => {
    const controller = new AbortController();
    queueMicrotask(() => {
      if (controller.signal.aborted) return;
      setWorkspace(undefined);
      setWorkspaceError(false);
      void getAdminBitbucketWorkspace({
        auth: accessToken,
        signal: controller.signal,
      })
        .then((result) => {
          if (controller.signal.aborted) return;
          if (result.data === undefined) setWorkspaceError(true);
          else setWorkspace(result.data.workspace);
        })
        .catch(() => {
          if (!controller.signal.aborted) setWorkspaceError(true);
        });
    });
    return () => controller.abort();
  }, [accessToken, reload]);

  useEffect(() => {
    const timer = setTimeout(() => setQuery(search.trim()), 300);
    return () => clearTimeout(timer);
  }, [search]);

  useEffect(() => {
    const controller = new AbortController();
    const ids: string[] = JSON.parse(selectedKey);
    void Promise.all(
      ids.map((id) =>
        getAdminRepository({
          auth: accessToken,
          path: { repository_id: id },
          signal: controller.signal,
        }),
      ),
    )
      .then((results) => {
        if (!controller.signal.aborted)
          setSelected(
            results.flatMap((result) =>
              result.data && result.data.provider !== "github"
                ? [result.data]
                : [],
            ),
          );
      })
      .catch(() => {
        /* Selection IDs stay in the wizard; the picker remains usable. */
      });
    return () => controller.abort();
  }, [accessToken, selectedKey]);

  const loadPage = useCallback(
    async (cursor: string | null, signal: AbortSignal) => {
      if (!workspace) return { items: [], next_cursor: null };
      const result = await listAdminBitbucketRepositories({
        auth: accessToken,
        query: { q: query, limit: 20, cursor },
        signal,
      });
      if (!result.data || result.data.workspace !== workspace)
        throw new Error("Repositories unavailable");
      return result.data;
    },
    [accessToken, workspace, query],
  );
  const collection = useCursorCollection({
    loadPage,
    getItemId: (item: AdminBitbucketRepositoryResponse) =>
      `${item.workspace}/${item.repository_slug}`,
    queryKey: JSON.stringify([accessToken, workspace, query, reload]),
  });

  async function selectRepository(
    repository: AdminBitbucketRepositoryResponse,
  ) {
    if (pendingRef.current) return;
    pendingRef.current = true;
    setPending(repository.repository_slug);
    setSelectionError(false);
    try {
      const result = await selectAdminBitbucketRepository({
        auth: accessToken,
        path: { repository_slug: repository.repository_slug },
        body: { workspace: repository.workspace },
      });
      if (!result.data) throw new Error("Repository unavailable");
      const saved = result.data;
      setSelected((current) => [
        ...current.filter((item) => item.id !== saved.id),
        saved,
      ]);
      onRepositorySelected?.(saved);
    } catch {
      setSelectionError(true);
    } finally {
      pendingRef.current = false;
      setPending(null);
    }
  }

  const Heading = embedded ? "h2" : "h1";
  const isSearching = query !== search.trim();
  return (
    <section
      className="grid min-w-0 gap-6"
      aria-label={t("Bitbucket repository connection")}
    >
      <Heading className="text-heading font-semibold">
        {t("Connect a Bitbucket repository")}
      </Heading>
      {workspaceError ? (
        <Alert variant="destructive">
          <AlertTitle>{t("Connection unavailable")}</AlertTitle>
          <AlertDescription>
            <Button
              variant="outline"
              onClick={() => setReload((value) => value + 1)}
            >
              {t("Retry")}
            </Button>
          </AlertDescription>
        </Alert>
      ) : workspace === undefined ? (
        <Skeleton className="h-32 w-full" aria-label={t("Loading workspace")} />
      ) : workspace === null ? (
        <Alert>
          <AlertTitle>{t("Configure the Bitbucket workspace")}</AlertTitle>
          <AlertDescription>
            <Button asChild variant="outline">
              <Link to="/admin/bitbucket">
                {t("Open Bitbucket connection")}
              </Link>
            </Button>
          </AlertDescription>
        </Alert>
      ) : (
        <>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <Badge variant="outline">
              {t("Workspace: ")}
              {workspace}
            </Badge>
            <Link
              className="text-sm text-primary underline"
              to="/admin/bitbucket"
            >
              {t("Configure workspace")}
            </Link>
          </div>
          <div className="grid gap-2">
            <Label htmlFor={searchId}>{t("Search repositories")}</Label>
            <Input
              id={searchId}
              type="search"
              maxLength={100}
              placeholder={t("Repository name or slug")}
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
          </div>
          {collection.status === "error" ? (
            <Alert variant="destructive">
              <AlertTitle>{t("Repositories unavailable")}</AlertTitle>
              <AlertDescription>
                <p>
                  {t(
                    "Check the workspace and Bitbucket connection, then try again.",
                  )}
                </p>
                <Button
                  variant="outline"
                  onClick={() => setReload((value) => value + 1)}
                >
                  {t("Retry")}
                </Button>
              </AlertDescription>
            </Alert>
          ) : collection.status === "loading" || isSearching ? (
            <p role="status">{t("Searching repositories…")}</p>
          ) : collection.isEmpty ? (
            <p role="status">{t("No repositories found.")}</p>
          ) : (
            <div
              className="max-h-80 overflow-y-auto rounded-lg border"
              aria-label={t("Bitbucket repositories")}
            >
              <ul className="divide-y">
                {collection.items.map((repository) => {
                  const linked = selected.some(
                    (item) =>
                      item.provider !== "github" &&
                      item.workspace === repository.workspace &&
                      item.repository_slug === repository.repository_slug,
                  );
                  return (
                    <li key={repository.repository_slug}>
                      <button
                        type="button"
                        className="flex min-h-14 w-full items-center justify-between gap-3 px-4 py-3 text-left hover:bg-muted focus-visible:outline-primary disabled:opacity-60"
                        disabled={pending !== null || linked}
                        aria-label={t("Connect {{v0}}", {
                          v0: repository.name,
                        })}
                        onClick={() => void selectRepository(repository)}
                      >
                        <span className="grid min-w-0 gap-1">
                          <strong className="break-words font-semibold">
                            {repository.name}
                          </strong>
                          <span className="break-all text-sm text-muted-foreground">
                            {repository.repository_slug}
                          </span>
                        </span>
                        <span className="shrink-0 text-sm text-primary">
                          {linked
                            ? t("Connected")
                            : pending === repository.repository_slug
                              ? t("Connecting…")
                              : t("Connect")}
                        </span>
                      </button>
                    </li>
                  );
                })}
              </ul>
            </div>
          )}
          {!isSearching && collection.isPartial ? (
            <Button
              variant="outline"
              disabled={collection.loadingMore}
              onClick={() => void collection.loadMore()}
            >
              {collection.loadingMore
                ? t("Loading…")
                : t("Load more repositories")}
            </Button>
          ) : null}
          {collection.loadMoreError ? (
            <p role="alert">
              {t(
                "Could not load more results. Retry: repositories already loaded remain available.",
              )}
            </p>
          ) : null}
        </>
      )}
      {selectionError ? (
        <Alert variant="destructive">
          <AlertTitle>{t("Repository not connected")}</AlertTitle>
          <AlertDescription>
            {t("Check the connection and try selecting the repository again.")}
          </AlertDescription>
        </Alert>
      ) : null}
      {selected.length > 0 ? (
        <section
          className="grid gap-3"
          aria-label={t("Connected repositories")}
        >
          <h3 className="font-semibold">{t("Connected repositories")}</h3>
          <div className="flex flex-wrap gap-2">
            {selected.map((item) => (
              <Badge
                key={item.id}
                variant="secondary"
                className="max-w-full whitespace-normal break-all"
              >
                {item.descriptive_name ?? item.repository_slug}
              </Badge>
            ))}
          </div>
        </section>
      ) : null}
    </section>
  );
}
