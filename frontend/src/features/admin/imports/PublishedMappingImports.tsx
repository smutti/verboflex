import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ElementType,
} from "react";
import { toast } from "sonner";

import {
  listAdminPublishedMappingImports,
  startAdminPublishedMappingImport,
  type AdminPublishedMappingImportListResponse,
  type AdminPublishedMappingImportResponse,
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
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "../../../components/ui/table";
import { importPollingIdentity, useImportPolling } from "./useImportPolling";

const IMPORT_PAGE_LIMIT = 50;
const MAX_IMPORT_PAGES = 50;

type ImportStatusFilter = "all" | "attention";
type CollectionState = "error" | "loading" | "ready";

interface PollingSnapshot {
  automaticUpdatesPaused: boolean;
  importRecord: AdminPublishedMappingImportResponse;
  pollingError: boolean;
  sourceProjectionKey: string;
}

export interface PublishedMappingImportsProps {
  accessToken: string;
  headingLevel?: "h2" | "h3";
  onReviewBaselineChange?: (item: AdminPublishedMappingImportResponse) => void;
  productId: string;
  repositories?: readonly AdminRepositoryResponse[];
  statusFilter?: ImportStatusFilter;
}

const STATUS_LABELS: Record<
  AdminPublishedMappingImportResponse["state"],
  string
> = {
  current: "Current",
  import_failed: "Import failed",
  may_be_stale: "May be stale",
  not_imported: "Not imported",
  queued: "Queued",
  review_required: "Review required",
  running: "Running",
};

const ACTION_LABELS: Record<
  AdminPublishedMappingImportResponse["action"],
  string
> = {
  import_in_progress: "Import in progress",
  refresh_import: "Refresh import",
  retry_import: "Retry import",
  review_baseline_change: "Review baseline change",
  run_import: "Run import",
};

const SIDE_LABELS = {
  direct: "Source",
  keys: "Keys",
  translations: "Translations",
} as const;

const ERROR_COPY: Record<
  NonNullable<AdminPublishedMappingImportResponse["error_category"]>,
  { heading: string; message: string }
> = {
  bounded_failure: {
    heading: "Import did not complete",
    message:
      "The source could not be read within the safe import limits. The last successful baseline is unchanged. Review the mapping before retrying.",
  },
  connection_required: {
    heading: "Bitbucket connection required",
    message:
      "The organizational Bitbucket connection is not ready for imports. An administrator must reconnect it before retrying this mapping.",
  },
  permission_denied: {
    heading: "Repository access denied",
    message:
      "Bitbucket denied access to this repository or branch. Review the organizational connection and repository permissions, then retry from this mapping.",
  },
  provider_unavailable: {
    heading: "Bitbucket unavailable",
    message:
      "Bitbucket could not complete this import. The last successful baseline is unchanged. Retry later.",
  },
  rate_limited: {
    heading: "Bitbucket request limit reached",
    message:
      "Bitbucket is temporarily limiting requests. Wait a few minutes, then retry this import from the mapping.",
  },
  source_not_found: {
    heading: "Import source not found",
    message:
      "The configured repository, branch, or localization file could not be found. Review the mapping configuration before retrying.",
  },
  timeout: {
    heading: "Import timed out",
    message:
      "Bitbucket did not respond within the safe time limit. The last successful baseline is unchanged. Retry later.",
  },
};

function fixedErrorCopy(item: AdminPublishedMappingImportResponse) {
  if (item.error_category === null) {
    return null;
  }
  const copy = ERROR_COPY[item.error_category];
  if (item.active_baseline !== null) {
    return copy;
  }
  return {
    ...copy,
    message: copy.message.replace(
      "The last successful baseline is unchanged.",
      "No import baseline was created.",
    ),
  };
}

function shortCommit(commit: string) {
  return commit.slice(0, 12);
}

function isStartAction(action: AdminPublishedMappingImportResponse["action"]) {
  return (
    action === "run_import" ||
    action === "refresh_import" ||
    action === "retry_import"
  );
}

function repositoryLabel(
  repositoryId: string,
  repositories: readonly AdminRepositoryResponse[],
) {
  const repository = repositories.find((item) => item.id === repositoryId);
  if (repository === undefined) {
    return repositoryId;
  }
  return (
    repository.descriptive_name ??
    `${repository.workspace}/${repository.repository_slug}`
  );
}

function baselineReferences(item: AdminPublishedMappingImportResponse) {
  const references = item.active_baseline?.source_references ?? [];
  const seen = new Set<string>();
  return references.filter((reference) => {
    const identity = `${reference.repository_side}:${reference.repository_id}:${reference.commit_hash}`;
    if (seen.has(identity)) {
      return false;
    }
    seen.add(identity);
    return true;
  });
}

function RepositorySides({
  item,
  repositories,
}: {
  item: AdminPublishedMappingImportResponse;
  repositories: readonly AdminRepositoryResponse[];
}) {
  return (
    <div className="grid gap-2">
      {item.repository_sides.map((side) => (
        <div
          key={`${side.role}:${side.repository_id}`}
          role="region"
          aria-label={`${SIDE_LABELS[side.role]} repository and branch`}
          // Opaque provider values use a local keyboard-scrollable boundary.
          // eslint-disable-next-line jsx-a11y/no-noninteractive-tabindex
          tabIndex={0}
          className="max-w-full overflow-x-auto rounded-md outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <div className="w-max min-w-full">
            <span className="font-semibold">{SIDE_LABELS[side.role]}</span>
            <span className="block [overflow-wrap:anywhere]">
              {repositoryLabel(side.repository_id, repositories)}
            </span>
            <span className="block font-mono [overflow-wrap:anywhere]">
              {side.source_branch}
            </span>
          </div>
        </div>
      ))}
    </div>
  );
}

function Baseline({ item }: { item: AdminPublishedMappingImportResponse }) {
  const references = baselineReferences(item);
  if (references.length === 0) {
    return <span>No successful import yet</span>;
  }
  return (
    <div className="grid gap-1">
      {references.map((reference) => (
        <span
          key={`${reference.repository_side}:${reference.repository_id}:${reference.commit_hash}`}
          className="block font-mono [overflow-wrap:anywhere]"
          title={reference.commit_hash}
        >
          <span className="font-sans font-semibold">
            {SIDE_LABELS[reference.repository_side]}{" "}
          </span>
          {shortCommit(reference.commit_hash)}
        </span>
      ))}
    </div>
  );
}

function LatestExecution({
  item,
}: {
  item: AdminPublishedMappingImportResponse;
}) {
  return (
    <div className="grid gap-1">
      <span>
        {item.latest_execution_at === null
          ? "Never"
          : new Date(item.latest_execution_at).toLocaleString()}
      </span>
      {item.retry_count > 0 ? <span>Retry {item.retry_count}</span> : null}
    </div>
  );
}

function RowError({
  focusRef,
  item,
  mutationFailed,
  pollingFailed,
}: {
  focusRef?: (element: HTMLDivElement | null) => void;
  item: AdminPublishedMappingImportResponse;
  mutationFailed: boolean;
  pollingFailed: boolean;
}) {
  const errorCopy = fixedErrorCopy(item);
  if (errorCopy === null && !mutationFailed && !pollingFailed) {
    return null;
  }
  const copy =
    errorCopy ??
    (pollingFailed
      ? {
          heading: "Status update unavailable",
          message:
            "Automatic status updates paused. Refresh status from this mapping.",
        }
      : {
          heading: "Import did not start",
          message:
            "The import request could not be accepted. The current baseline is unchanged.",
        });
  return (
    <Alert
      ref={focusRef}
      tabIndex={mutationFailed ? -1 : undefined}
      variant={item.active_baseline === null ? "destructive" : "default"}
    >
      <AlertTitle>{copy.heading}</AlertTitle>
      <AlertDescription>{copy.message}</AlertDescription>
    </Alert>
  );
}

function ImportAction({
  automaticUpdatesPaused,
  item,
  onAction,
  onRefreshStatus,
  pending,
}: {
  automaticUpdatesPaused: boolean;
  item: AdminPublishedMappingImportResponse;
  onAction: () => void;
  onRefreshStatus: () => void;
  pending: boolean;
}) {
  const inProgress = item.action === "import_in_progress";
  return (
    <div className="grid gap-2">
      <Button
        type="button"
        variant="outline"
        className="min-h-11 w-full whitespace-normal"
        disabled={pending || inProgress}
        aria-busy={pending || inProgress}
        onClick={onAction}
      >
        {ACTION_LABELS[item.action]}
      </Button>
      {automaticUpdatesPaused && inProgress ? (
        <>
          <span className="text-sm text-muted-foreground">
            Automatic status updates paused
          </span>
          <Button
            type="button"
            variant="outline"
            className="min-h-11 w-full whitespace-normal"
            onClick={onRefreshStatus}
          >
            Refresh status
          </Button>
        </>
      ) : null}
    </div>
  );
}

function ImportPollingBridge({
  accessToken,
  item,
  onAnnouncement,
  onPollingState,
  productId,
  registerRefresh,
}: {
  accessToken: string;
  item: AdminPublishedMappingImportResponse;
  onAnnouncement: (state: string) => void;
  onPollingState: (mappingId: string, snapshot: PollingSnapshot) => void;
  productId: string;
  registerRefresh: (
    mappingId: string,
    refresh: (() => Promise<void>) | null,
  ) => void;
}) {
  const polling = useImportPolling({
    accessToken,
    initialImport: item,
    onAnnouncement: (state) =>
      onAnnouncement(`${state} for mapping ${item.mapping_id}`),
    productId,
  });
  const sourceProjectionKey = JSON.stringify(item);

  useEffect(() => {
    onPollingState(item.mapping_id, {
      automaticUpdatesPaused: polling.automaticUpdatesPaused,
      importRecord: polling.importRecord,
      pollingError: polling.pollingError,
      sourceProjectionKey,
    });
  }, [
    item.mapping_id,
    onPollingState,
    polling.automaticUpdatesPaused,
    polling.importRecord,
    polling.pollingError,
    sourceProjectionKey,
  ]);

  useEffect(() => {
    registerRefresh(item.mapping_id, polling.refreshStatus);
    return () => registerRefresh(item.mapping_id, null);
  }, [item.mapping_id, polling.refreshStatus, registerRefresh]);

  return null;
}

export function PublishedMappingImports({
  accessToken,
  headingLevel = "h2",
  onReviewBaselineChange,
  productId,
  repositories = [],
  statusFilter = "all",
}: PublishedMappingImportsProps) {
  const controllerRef = useRef<AbortController | null>(null);
  const generationRef = useRef(0);
  const pendingRef = useRef(new Set<string>());
  const refreshHandlersRef = useRef(new Map<string, () => Promise<void>>());
  const mutationErrorRefs = useRef(new Map<string, HTMLDivElement>());
  const [collectionState, setCollectionState] =
    useState<CollectionState>("loading");
  const [items, setItems] = useState<AdminPublishedMappingImportResponse[]>([]);
  const [pendingMappings, setPendingMappings] = useState<ReadonlySet<string>>(
    new Set(),
  );
  const [mutationFailures, setMutationFailures] = useState<ReadonlySet<string>>(
    new Set(),
  );
  const [statusRefreshFailures, setStatusRefreshFailures] = useState<
    ReadonlySet<string>
  >(new Set());
  const [pollingSnapshots, setPollingSnapshots] = useState<
    ReadonlyMap<string, PollingSnapshot>
  >(new Map());
  const [announcement, setAnnouncement] = useState("");

  const loadCompleteCollection = useCallback(
    async (preserveVisibleState = false) => {
      const generation = ++generationRef.current;
      controllerRef.current?.abort();
      const controller = new AbortController();
      controllerRef.current = controller;
      if (!preserveVisibleState) {
        setCollectionState("loading");
      }

      try {
        const collected: AdminPublishedMappingImportResponse[] = [];
        const seenMappings = new Set<string>();
        const seenCursors = new Set<string>();
        let expectedRevision: string | null = null;
        let cursor: string | null = null;

        for (
          let pageNumber = 0;
          pageNumber < MAX_IMPORT_PAGES;
          pageNumber += 1
        ) {
          const result: { data?: AdminPublishedMappingImportListResponse } =
            await listAdminPublishedMappingImports({
              auth: accessToken,
              path: { product_id: productId },
              query: { cursor, limit: IMPORT_PAGE_LIMIT, status: statusFilter },
              signal: controller.signal,
            });
          if (
            controller.signal.aborted ||
            generationRef.current !== generation
          ) {
            return false;
          }
          if (result.data === undefined) {
            throw new Error("published imports unavailable");
          }
          for (const item of result.data.items) {
            if (expectedRevision === null) {
              expectedRevision = item.active_revision_id;
            } else if (item.active_revision_id !== expectedRevision) {
              throw new Error("published import revision changed");
            }
            if (!seenMappings.has(item.mapping_id)) {
              seenMappings.add(item.mapping_id);
              collected.push(item);
            }
          }
          const nextCursor: string | null = result.data.next_cursor ?? null;
          if (nextCursor === null) {
            setItems(collected);
            setCollectionState("ready");
            setMutationFailures(new Set());
            setStatusRefreshFailures(new Set());
            return true;
          }
          if (
            nextCursor.trim().length === 0 ||
            seenCursors.has(nextCursor) ||
            pageNumber === MAX_IMPORT_PAGES - 1
          ) {
            throw new Error("invalid import cursor chain");
          }
          seenCursors.add(nextCursor);
          cursor = nextCursor;
        }
        throw new Error("published import page limit exceeded");
      } catch {
        if (
          !controller.signal.aborted &&
          generationRef.current === generation
        ) {
          if (!preserveVisibleState) {
            setItems([]);
            setCollectionState("error");
          }
        }
        return false;
      } finally {
        if (controllerRef.current === controller) {
          controllerRef.current = null;
        }
      }
    },
    [accessToken, productId, statusFilter],
  );

  useEffect(() => {
    const scheduledGeneration = generationRef.current;
    queueMicrotask(() => {
      if (generationRef.current === scheduledGeneration) {
        void loadCompleteCollection();
      }
    });
    return () => {
      generationRef.current += 1;
      controllerRef.current?.abort();
    };
  }, [loadCompleteCollection]);

  const updatePollingState = useCallback(
    (mappingId: string, snapshot: PollingSnapshot) => {
      setPollingSnapshots((current) => {
        const previous = current.get(mappingId);
        if (
          previous?.automaticUpdatesPaused ===
            snapshot.automaticUpdatesPaused &&
          previous.pollingError === snapshot.pollingError &&
          previous.sourceProjectionKey === snapshot.sourceProjectionKey &&
          JSON.stringify(previous.importRecord) ===
            JSON.stringify(snapshot.importRecord)
        ) {
          return current;
        }
        const next = new Map(current);
        next.set(mappingId, snapshot);
        return next;
      });
    },
    [],
  );

  const registerRefresh = useCallback(
    (mappingId: string, refresh: (() => Promise<void>) | null) => {
      if (refresh === null) {
        refreshHandlersRef.current.delete(mappingId);
      } else {
        refreshHandlersRef.current.set(mappingId, refresh);
      }
    },
    [],
  );

  const visibleItems = useMemo(
    () =>
      items.map((item) => {
        const snapshot = pollingSnapshots.get(item.mapping_id);
        if (
          snapshot === undefined ||
          snapshot.sourceProjectionKey !== JSON.stringify(item) ||
          importPollingIdentity(productId, snapshot.importRecord) !==
            importPollingIdentity(productId, item)
        ) {
          return {
            automaticUpdatesPaused: false,
            importRecord: item,
            pollingError: false,
          };
        }
        return snapshot;
      }),
    [items, pollingSnapshots, productId],
  );

  const setMutationErrorRef = useCallback(
    (mappingId: string, element: HTMLDivElement | null) => {
      if (element === null) {
        mutationErrorRefs.current.delete(mappingId);
      } else {
        mutationErrorRefs.current.set(mappingId, element);
      }
    },
    [],
  );

  const startImport = useCallback(
    async (item: AdminPublishedMappingImportResponse) => {
      if (
        !isStartAction(item.action) ||
        pendingRef.current.has(item.mapping_id)
      ) {
        return;
      }
      pendingRef.current.add(item.mapping_id);
      setPendingMappings(new Set(pendingRef.current));
      setMutationFailures((current) => {
        const next = new Set(current);
        next.delete(item.mapping_id);
        return next;
      });
      setStatusRefreshFailures((current) => {
        const next = new Set(current);
        next.delete(item.mapping_id);
        return next;
      });
      let accepted = false;
      try {
        const result = await startAdminPublishedMappingImport({
          auth: accessToken,
          path: { mapping_id: item.mapping_id, product_id: productId },
        });
        if (result.data === undefined) {
          throw new Error("import unavailable");
        }
        accepted = true;
        toast.success("Import started");
        const refreshed = await loadCompleteCollection(true);
        if (!refreshed) {
          throw new Error("import status unavailable");
        }
      } catch {
        const setFailure = accepted
          ? setStatusRefreshFailures
          : setMutationFailures;
        setFailure((current) => {
          const next = new Set(current);
          next.add(item.mapping_id);
          return next;
        });
        queueMicrotask(() =>
          mutationErrorRefs.current.get(item.mapping_id)?.focus(),
        );
      } finally {
        pendingRef.current.delete(item.mapping_id);
        setPendingMappings(new Set(pendingRef.current));
      }
    },
    [accessToken, loadCompleteCollection, productId],
  );

  const Heading = headingLevel as ElementType;

  return (
    <section className="grid min-w-0 max-w-full gap-4 overflow-x-clip">
      <div className="grid gap-2">
        <Heading className="text-heading font-semibold">
          Published mapping imports
        </Heading>
        <p className="text-muted-foreground">
          Import localization sources from the exact published branch.
        </p>
      </div>

      {collectionState === "loading" ? (
        <div className="grid gap-3" role="status" aria-live="polite">
          <Skeleton
            data-testid="published-import-skeleton"
            className="h-24 w-full"
          />
          <span>Loading published mappings</span>
        </div>
      ) : null}

      {collectionState === "error" ? (
        <Alert variant="destructive">
          <AlertTitle>
            <h4>Published imports unavailable</h4>
          </AlertTitle>
          <AlertDescription>
            <p>
              We could not load this page. Retry without leaving the
              administration area.
            </p>
            <Button
              type="button"
              variant="outline"
              className="min-h-11 whitespace-normal"
              onClick={() => void loadCompleteCollection()}
            >
              Retry loading published imports
            </Button>
          </AlertDescription>
        </Alert>
      ) : null}

      {collectionState === "ready" && items.length === 0 ? (
        <div className="grid gap-2 rounded-lg border bg-secondary p-6">
          <h4 className="font-semibold">No published mappings to import</h4>
          <p className="text-muted-foreground">
            Publish a validated mapping before running an import.
          </p>
        </div>
      ) : null}

      {collectionState === "ready" && items.length > 0 ? (
        <>
          {items.map((item) => (
            <ImportPollingBridge
              key={item.mapping_id}
              accessToken={accessToken}
              item={item}
              onAnnouncement={setAnnouncement}
              onPollingState={updatePollingState}
              productId={productId}
              registerRefresh={registerRefresh}
            />
          ))}

          <div className="hidden max-w-full overflow-x-auto md:block">
            <Table aria-label="Published mapping imports">
              <TableHeader>
                <TableRow>
                  <TableHead>Mapping</TableHead>
                  <TableHead>Import status</TableHead>
                  <TableHead>Last successful baseline</TableHead>
                  <TableHead>Latest execution</TableHead>
                  <TableHead>Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {visibleItems.map(
                  ({
                    automaticUpdatesPaused,
                    importRecord: item,
                    pollingError,
                  }) => {
                    const pending = pendingMappings.has(item.mapping_id);
                    return (
                      <TableRow
                        key={item.mapping_id}
                        data-mapping-id={item.mapping_id}
                        data-testid={`published-import-row-${item.mapping_id}`}
                      >
                        <TableCell className="max-w-sm whitespace-normal align-top">
                          <RepositorySides
                            item={item}
                            repositories={repositories}
                          />
                          <RowError
                            focusRef={(element) =>
                              setMutationErrorRef(item.mapping_id, element)
                            }
                            item={item}
                            mutationFailed={mutationFailures.has(
                              item.mapping_id,
                            )}
                            pollingFailed={
                              pollingError ||
                              statusRefreshFailures.has(item.mapping_id)
                            }
                          />
                        </TableCell>
                        <TableCell className="align-top">
                          <Badge variant="outline">
                            {STATUS_LABELS[item.state]}
                          </Badge>
                        </TableCell>
                        <TableCell className="max-w-xs whitespace-normal align-top">
                          <Baseline item={item} />
                        </TableCell>
                        <TableCell className="align-top">
                          <LatestExecution item={item} />
                        </TableCell>
                        <TableCell className="align-top">
                          <ImportAction
                            automaticUpdatesPaused={automaticUpdatesPaused}
                            item={item}
                            onAction={() => {
                              if (item.action === "review_baseline_change") {
                                onReviewBaselineChange?.(item);
                              } else {
                                void startImport(item);
                              }
                            }}
                            onRefreshStatus={() =>
                              void refreshHandlersRef.current.get(
                                item.mapping_id,
                              )?.()
                            }
                            pending={pending}
                          />
                        </TableCell>
                      </TableRow>
                    );
                  },
                )}
              </TableBody>
            </Table>
          </div>

          <section
            aria-label="Published mapping imports mobile list"
            className="grid min-w-0 max-w-full gap-3 overflow-x-clip md:hidden"
          >
            {visibleItems.map(
              ({
                automaticUpdatesPaused,
                importRecord: item,
                pollingError,
              }) => (
                <article
                  key={item.mapping_id}
                  className="grid min-w-0 max-w-full gap-4 rounded-lg border bg-secondary p-4"
                >
                  <div className="grid min-w-0 gap-1">
                    <span className="text-sm font-semibold">Mapping</span>
                    <RepositorySides item={item} repositories={repositories} />
                  </div>
                  <div className="grid gap-1">
                    <span className="text-sm font-semibold">Import status</span>
                    <Badge className="w-fit" variant="outline">
                      {STATUS_LABELS[item.state]}
                    </Badge>
                  </div>
                  <div className="grid min-w-0 gap-1">
                    <span className="text-sm font-semibold">
                      Last successful baseline
                    </span>
                    <Baseline item={item} />
                  </div>
                  <div className="grid gap-1">
                    <span className="text-sm font-semibold">
                      Latest execution
                    </span>
                    <LatestExecution item={item} />
                  </div>
                  <RowError
                    item={item}
                    mutationFailed={mutationFailures.has(item.mapping_id)}
                    pollingFailed={
                      pollingError || statusRefreshFailures.has(item.mapping_id)
                    }
                  />
                  <ImportAction
                    automaticUpdatesPaused={automaticUpdatesPaused}
                    item={item}
                    onAction={() => {
                      if (item.action === "review_baseline_change") {
                        onReviewBaselineChange?.(item);
                      } else {
                        void startImport(item);
                      }
                    }}
                    onRefreshStatus={() =>
                      void refreshHandlersRef.current.get(item.mapping_id)?.()
                    }
                    pending={pendingMappings.has(item.mapping_id)}
                  />
                </article>
              ),
            )}
          </section>

          <p className="sr-only" aria-live="polite" aria-atomic="true">
            {announcement}
          </p>
        </>
      ) : null}
    </section>
  );
}
