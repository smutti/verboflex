import { t, useUiLanguage, getUiLanguage } from "@/i18n";
import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  type ElementType,
} from "react";
import { toast } from "sonner";
import { Link } from "react-router-dom";

import {
  listAdminPublishedMappingImports,
  startAdminPublishedMappingImport,
  type AdminPublishedMappingImportListResponse,
  type AdminPublishedMappingImportResponse,
  type AdminRepositoryResponse,
  type ImportParserIssue,
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
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "../../../components/ui/tabs";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "../../../components/ui/table";
import {
  hasLivePublishedAuthority,
  ownsLiveMutationController,
  ownsPublishedRequestToken,
} from "./mutationAuthority";
import { importPollingIdentity, useImportPolling } from "./useImportPolling";
import { RewrittenBaselineDialog } from "./RewrittenBaselineDialog";
import { DuplicateKeysDialog } from "./DuplicateKeysDialog";
import { useSession } from "../../auth/session";

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
  compact?: boolean;
  /** Start only sources that have never been imported; resume existing jobs. */
  autoStart?: boolean;
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
  get current() {
    return t("Current");
  },
  get import_failed() {
    return t("Import failed");
  },
  get may_be_stale() {
    return t("May be stale");
  },
  get not_imported() {
    return t("Not imported");
  },
  get queued() {
    return t("Queued");
  },
  get review_required() {
    return t("Review required");
  },
  get running() {
    return t("Running");
  },
};

const ACTION_LABELS: Record<
  AdminPublishedMappingImportResponse["action"],
  string
> = {
  get import_in_progress() {
    return t("Import in progress");
  },
  get refresh_import() {
    return t("Refresh import");
  },
  get retry_import() {
    return t("Retry import");
  },
  get review_baseline_change() {
    return t("Review baseline change");
  },
  get run_import() {
    return t("Run import");
  },
};

const SIDE_LABELS = {
  get direct() {
    return t("Source");
  },
  get keys() {
    return t("Keys");
  },
  get translations() {
    return t("Translations");
  },
} as const;

const PARSER_CATEGORIES: Record<ImportParserIssue["issue_code"], string> = {
  get malformed_file() {
    return t("Malformed file");
  },
  get ambiguous_structure() {
    return t("Ambiguous structure");
  },
  get unsupported_structure() {
    return t("Unsupported structure");
  },
  get duplicate_key() {
    return t("Duplicate key");
  },
  get base_language_required() {
    return t("Base language required");
  },
};

function hasParserFailure(item: AdminPublishedMappingImportResponse) {
  return (
    (item.state === "import_failed" || item.state === "may_be_stale") &&
    (item.parser_issues.length > 0 ||
      item.parser_issue_remaining_count > 0 ||
      item.error_category === null)
  );
}

function isImportActive(item: AdminPublishedMappingImportResponse) {
  return item.state === "queued" || item.state === "running";
}

function importProgress(item: AdminPublishedMappingImportResponse) {
  switch (item.state) {
    case "not_imported":
      return { step: 0, label: t("Ready to start") };
    case "queued":
      return {
        step: 1,
        label: t("Step 1 of 3: Waiting for the import worker"),
      };
    case "running":
      return {
        step: 2,
        label: t("Step 2 of 3: Reading and validating repository files"),
      };
    case "current":
      return {
        step: 3,
        label: t("Step 3 of 3: Imported strings are available"),
      };
    case "review_required":
      return { step: 3, label: t("Step 3 of 3: Source changes need review") };
    case "import_failed":
    case "may_be_stale":
      return { step: 3, label: t("Step 3 of 3: Completed with warnings") };
  }
}

function parserWarningCount(item: AdminPublishedMappingImportResponse) {
  return (
    (item.parser_issues?.length ?? 0) + (item.parser_issue_remaining_count ?? 0)
  );
}

function hasImportWarnings(item: AdminPublishedMappingImportResponse) {
  return (
    parserWarningCount(item) > 0 ||
    (item.duplicate_report_summary?.group_count ?? 0) > 0 ||
    item.state === "import_failed" ||
    item.state === "may_be_stale" ||
    item.state === "review_required"
  );
}

function ImportProgress({
  item,
  repositories,
}: {
  item: AdminPublishedMappingImportResponse;
  repositories: readonly AdminRepositoryResponse[];
}) {
  useUiLanguage();
  const progress = importProgress(item);
  const primarySide = item.repository_sides[0];
  return (
    <div className="grid min-w-0 gap-2 rounded-lg border bg-card p-4">
      <div className="flex min-w-0 flex-wrap items-center justify-between gap-2">
        <div className="grid min-w-0 gap-1">
          <span className="font-semibold [overflow-wrap:anywhere]">
            {primarySide
              ? repositoryLabel(primarySide.repository_id, repositories)
              : t("Published mapping")}
          </span>
          {primarySide ? (
            <span className="font-mono text-sm [overflow-wrap:anywhere]">
              {primarySide.source_branch}
            </span>
          ) : null}
        </div>
        <Badge variant="outline">{STATUS_LABELS[item.state]}</Badge>
      </div>
      <div
        role="progressbar"
        aria-label={t("Import progress for mapping {{v0}}", {
          v0: item.mapping_id,
        })}
        aria-valuemin={0}
        aria-valuemax={3}
        aria-valuenow={progress.step}
        aria-valuetext={progress.label}
        className="h-2 overflow-hidden rounded-full bg-muted"
      >
        <div
          aria-hidden="true"
          className="h-full rounded-full bg-primary transition-[width] duration-300 motion-reduce:transition-none"
          style={{ width: `${(progress.step / 3) * 100}%` }}
        />
      </div>
      <p className="text-sm text-muted-foreground">{progress.label}</p>
    </div>
  );
}

function preserveNewerImport(
  current: AdminPublishedMappingImportResponse,
  incoming: AdminPublishedMappingImportResponse,
) {
  if (current.active_revision_id !== incoming.active_revision_id)
    return incoming;
  const currentExecution = current.execution_number ?? 0;
  const incomingExecution = incoming.execution_number ?? 0;
  if (currentExecution > incomingExecution) return current;
  if (
    currentExecution === incomingExecution &&
    ((!isImportActive(current) && isImportActive(incoming)) ||
      (current.state === "running" && incoming.state === "queued"))
  )
    return current;
  return incoming;
}

function ConfigureBaseLanguage({ productId }: { productId: string }) {
  useUiLanguage();
  const { state } = useSession();
  if (
    state.status !== "authenticated" ||
    !state.principal.roles.includes("admin")
  ) {
    return null;
  }
  return (
    <Button
      asChild
      variant="outline"
      className="min-h-[44px] h-auto whitespace-normal motion-reduce:transition-none"
    >
      <Link to={`/admin/products/${encodeURIComponent(productId)}/preview`}>
        {t("Configure base language")}
      </Link>
    </Button>
  );
}

function ParserIssues({
  item,
  productId,
}: {
  item: AdminPublishedMappingImportResponse;
  productId: string;
}) {
  useUiLanguage();
  // Stable sort preserves the provider-file order projected within each side.
  const sideOrder = { direct: 0, keys: 1, translations: 2 };
  const issues = [...item.parser_issues]
    .sort((a, b) => sideOrder[a.repository_side] - sideOrder[b.repository_side])
    .slice(0, 5);
  const remaining =
    item.parser_issue_remaining_count +
    Math.max(0, item.parser_issues.length - issues.length);
  return (
    <>
      {issues.length > 0 ? (
        <ul
          aria-label={t("Parser errors")}
          className="grid min-w-0 w-full gap-2"
        >
          {issues.map((issue, index) => (
            <li key={index} className="min-w-0 [overflow-wrap:anywhere]">
              <span className="font-semibold">
                {PARSER_CATEGORIES[issue.issue_code]}
              </span>
              <span className="block">
                {SIDE_LABELS[issue.repository_side]}
              </span>
              <span className="block font-mono">{issue.path}</span>
              {issue.line !== null ? (
                <span>
                  {t("Line ")}
                  {issue.line}
                  {issue.column !== null
                    ? t(", column {{v0}}", { v0: issue.column })
                    : ""}
                </span>
              ) : issue.column !== null ? (
                <span>
                  {t("Column ")}
                  {issue.column}
                </span>
              ) : null}
            </li>
          ))}
        </ul>
      ) : null}
      {remaining > 0 ? (
        <p>
          {t("And ")}
          {remaining} {t(" more errors.")}
        </p>
      ) : null}
      {item.parser_issues.some(
        (issue) => issue.issue_code === "base_language_required",
      ) ? (
        <ConfigureBaseLanguage productId={productId} />
      ) : null}
    </>
  );
}

const ERROR_COPY: Record<
  NonNullable<AdminPublishedMappingImportResponse["error_category"]>,
  { heading: string; message: string }
> = {
  bounded_failure: {
    get heading() {
      return t("Import did not complete");
    },
    get message() {
      return t(
        "The source could not be read within the safe import limits. The last successful baseline is unchanged. Review the mapping before retrying.",
      );
    },
  },
  connection_required: {
    get heading() {
      return t("Bitbucket connection required");
    },
    get message() {
      return t(
        "The organizational Bitbucket connection is not ready for imports. An administrator must reconnect it before retrying this mapping.",
      );
    },
  },
  permission_denied: {
    get heading() {
      return t("Repository access denied");
    },
    get message() {
      return t(
        "Bitbucket denied access to this repository or branch. Review the organizational connection and repository permissions, then retry from this mapping.",
      );
    },
  },
  provider_unavailable: {
    get heading() {
      return t("Bitbucket unavailable");
    },
    get message() {
      return t(
        "Bitbucket could not complete this import. The last successful baseline is unchanged. Retry later.",
      );
    },
  },
  rate_limited: {
    get heading() {
      return t("Bitbucket request limit reached");
    },
    get message() {
      return t(
        "Bitbucket is temporarily limiting requests. Wait a few minutes, then retry this import from the mapping.",
      );
    },
  },
  source_not_found: {
    get heading() {
      return t("Import source not found");
    },
    get message() {
      return t(
        "The configured repository, branch, or localization file could not be found. Review the mapping configuration before retrying.",
      );
    },
  },
  timeout: {
    get heading() {
      return t("Import timed out");
    },
    get message() {
      return t(
        "Bitbucket did not respond within the safe time limit. The last successful baseline is unchanged. Retry later.",
      );
    },
  },
};

function fixedErrorCopy(item: AdminPublishedMappingImportResponse) {
  if (hasParserFailure(item)) {
    return {
      heading: t("Localization files could not be imported"),
      message: t(
        "One or more configured files are malformed, ambiguous, or contain unsupported structure. {{v0}}",
        {
          v0:
            item.dataset_status === "retained"
              ? "The last successful translation dataset remains active."
              : "No translation dataset was created.",
        },
      ),
    };
  }
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
      t("The last successful baseline is unchanged."),
      t("No import baseline was created."),
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
  useUiLanguage();
  return (
    <div className="grid gap-2">
      {item.repository_sides.map((side) => (
        <div
          key={`${side.role}:${side.repository_id}`}
          role="region"
          aria-label={t("{{v0}} repository and branch", {
            v0: SIDE_LABELS[side.role],
          })}
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
  useUiLanguage();
  const references = baselineReferences(item);
  if (references.length === 0) {
    return <span>{t("No successful import yet")}</span>;
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
  useUiLanguage();
  return (
    <div className="grid gap-1">
      <span>
        {item.latest_execution_at === null
          ? t("Never")
          : new Date(item.latest_execution_at).toLocaleString(getUiLanguage())}
      </span>
      {item.retry_count > 0 ? (
        <span>
          {t("Retry ")}
          {item.retry_count}
        </span>
      ) : null}
    </div>
  );
}

function RowError({
  focusRef,
  item,
  mutationFailed,
  pollingFailed,
  productId,
}: {
  focusRef?: (element: HTMLDivElement | null) => void;
  item: AdminPublishedMappingImportResponse;
  mutationFailed: boolean;
  pollingFailed: boolean;
  productId: string;
}) {
  useUiLanguage();
  const errorCopy = fixedErrorCopy(item);
  if (errorCopy === null && !mutationFailed && !pollingFailed) {
    return null;
  }
  const copy =
    errorCopy ??
    (pollingFailed
      ? {
          heading: t("Status update unavailable"),
          message: t(
            "Automatic status updates paused. Refresh status from this mapping.",
          ),
        }
      : {
          heading: t("Import did not start"),
          message: t(
            "The import request could not be accepted. The current baseline is unchanged.",
          ),
        });
  return (
    <Alert
      ref={focusRef}
      tabIndex={-1}
      variant={item.active_baseline === null ? "destructive" : "default"}
      className="min-w-0 [overflow-wrap:anywhere]"
    >
      <AlertTitle className="line-clamp-none">{copy.heading}</AlertTitle>
      <AlertDescription className="min-w-0">
        <p>{copy.message}</p>
        {hasParserFailure(item) ? (
          <ParserIssues item={item} productId={productId} />
        ) : null}
      </AlertDescription>
    </Alert>
  );
}

function AdminDuplicateAction({
  accessToken,
  productId,
  item,
}: {
  accessToken: string;
  productId: string;
  item: AdminPublishedMappingImportResponse;
}) {
  useUiLanguage();
  const { state } = useSession();
  if (
    state.status !== "authenticated" ||
    !state.principal.roles.includes("admin")
  )
    return null;
  return (
    <DuplicateKeysDialog
      accessToken={accessToken}
      productId={productId}
      importId={item.id!}
      execution={item.execution_number!}
    />
  );
}

function ImportAction({
  accessToken,
  productId,
  automaticUpdatesPaused,
  item,
  onAction,
  onRefreshStatus,
  pending,
}: {
  accessToken: string;
  productId: string;
  automaticUpdatesPaused: boolean;
  item: AdminPublishedMappingImportResponse;
  onAction: (trigger: HTMLButtonElement) => void;
  onRefreshStatus: () => void;
  pending: boolean;
}) {
  useUiLanguage();
  const inProgress = item.action === "import_in_progress";
  return (
    <div className="grid gap-2">
      {item.id !== null &&
      item.execution_number &&
      hasParserFailure(item) &&
      item.parser_issues.some(
        (issue) => issue.issue_code === "duplicate_key",
      ) ? (
        <AdminDuplicateAction
          accessToken={accessToken}
          productId={productId}
          item={item}
        />
      ) : null}
      <Button
        type="button"
        variant="outline"
        className="min-h-[44px] h-auto w-full whitespace-normal motion-reduce:transition-none"
        disabled={pending || inProgress}
        aria-busy={pending || inProgress}
        onClick={(event) => onAction(event.currentTarget)}
      >
        {ACTION_LABELS[item.action]}
      </Button>
      {automaticUpdatesPaused && inProgress ? (
        <>
          <span className="text-sm text-muted-foreground">
            {t("Automatic status updates paused")}
          </span>
          <Button
            type="button"
            variant="outline"
            className="min-h-[44px] h-auto w-full whitespace-normal motion-reduce:transition-none"
            onClick={onRefreshStatus}
          >
            {t("Refresh status")}
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
  useUiLanguage();
  const polling = useImportPolling({
    accessToken,
    initialImport: item,
    onAnnouncement: (state) =>
      onAnnouncement(
        t("{{v0}} for mapping {{v1}}", { v0: state, v1: item.mapping_id }),
      ),
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
  compact = false,
  autoStart = false,
  accessToken,
  headingLevel = "h2",
  onReviewBaselineChange,
  productId,
  repositories = [],
  statusFilter = "all",
}: PublishedMappingImportsProps) {
  useUiLanguage();
  const authorityIdentity = useMemo(
    () => JSON.stringify({ accessToken, productId, statusFilter }),
    [accessToken, productId, statusFilter],
  );
  const authorityIdentityRef = useRef(authorityIdentity);
  useLayoutEffect(() => {
    authorityIdentityRef.current = authorityIdentity;
  }, [authorityIdentity]);
  const controllerRef = useRef<AbortController | null>(null);
  const generationRef = useRef(0);
  const loadedAuthorityRef = useRef<string | null>(null);
  const pendingRef = useRef(
    new Map<
      string,
      {
        authorityIdentity: string;
        controller: AbortController;
        requestToken: symbol;
      }
    >(),
  );
  const refreshHandlersRef = useRef(new Map<string, () => Promise<void>>());
  const desktopMutationErrorRefs = useRef(new Map<string, HTMLDivElement>());
  const mobileMutationErrorRefs = useRef(new Map<string, HTMLDivElement>());
  const pendingErrorFocusRef = useRef<string | null>(null);
  const initiatedImportsRef = useRef(
    new Map<string, { identity: string; trigger: HTMLButtonElement | null }>(),
  );
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
  const [rewriteReview, setRewriteReview] = useState<{
    importRecord: AdminPublishedMappingImportResponse;
    triggerElement: HTMLButtonElement;
  } | null>(null);

  useEffect(() => {
    let active = true;
    const pendingRequests = pendingRef.current;
    const initiatedImports = initiatedImportsRef.current;
    queueMicrotask(() => {
      if (active) {
        setPendingMappings(
          new Set(
            [...pendingRequests]
              .filter(
                ([, pending]) =>
                  pending.authorityIdentity === authorityIdentity,
              )
              .map(([mappingId]) => mappingId),
          ),
        );
      }
    });
    return () => {
      active = false;
      for (const pending of pendingRequests.values()) {
        pending.controller.abort();
      }
      pendingRequests.clear();
      initiatedImports.clear();
      pendingErrorFocusRef.current = null;
    };
  }, [authorityIdentity]);

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
            setItems((current) =>
              collected.map((incoming) => {
                const previous = current.find(
                  (item) => item.mapping_id === incoming.mapping_id,
                );
                return preserveVisibleState && previous !== undefined
                  ? preserveNewerImport(previous, incoming)
                  : incoming;
              }),
            );
            loadedAuthorityRef.current = authorityIdentity;
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
    [accessToken, authorityIdentity, productId, statusFilter],
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
      // Persist terminal observation so a slower collection response cannot restart it.
      if (!isImportActive(snapshot.importRecord)) {
        setItems((current) =>
          current.map((item) =>
            item.mapping_id === mappingId &&
            JSON.stringify(item) === snapshot.sourceProjectionKey
              ? preserveNewerImport(item, snapshot.importRecord)
              : item,
          ),
        );
      }
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
  const visibleImportRecords = visibleItems.map((item) => item.importRecord);
  const warningItems = visibleImportRecords.filter(hasImportWarnings);
  const importedMappingCount = visibleImportRecords.filter(
    (item) =>
      item.active_baseline != null &&
      (item.dataset_status === "active" || item.dataset_status === "retained"),
  ).length;

  useEffect(() => {
    for (const { importRecord } of visibleItems) {
      const initiated = initiatedImportsRef.current.get(
        importRecord.mapping_id,
      );
      if (
        initiated === undefined ||
        isImportActive(importRecord) ||
        initiated.identity !== importPollingIdentity(productId, importRecord)
      )
        continue;
      initiatedImportsRef.current.delete(importRecord.mapping_id);
      if (
        initiated.trigger === null ||
        !initiated.trigger.isConnected ||
        (document.activeElement !== initiated.trigger &&
          document.activeElement !== document.body)
      )
        continue;
      const alert = initiated.trigger
        .closest("tr, article")
        ?.querySelector<HTMLDivElement>('[role="alert"]');
      if (alert !== null && alert !== undefined) alert.focus();
      else initiated.trigger.focus();
    }
  }, [visibleItems, productId]);

  const setMutationErrorRef = useCallback(
    (
      surface: "desktop" | "mobile",
      mappingId: string,
      element: HTMLDivElement | null,
    ) => {
      const refs =
        surface === "desktop"
          ? desktopMutationErrorRefs.current
          : mobileMutationErrorRefs.current;
      if (element === null) {
        refs.delete(mappingId);
      } else {
        refs.set(mappingId, element);
      }
    },
    [],
  );

  const focusMutationError = useCallback((mappingId: string) => {
    const candidates = [
      mobileMutationErrorRefs.current.get(mappingId),
      desktopMutationErrorRefs.current.get(mappingId),
    ].filter(
      (element): element is HTMLDivElement =>
        element !== undefined && element.isConnected,
    );
    const focusTarget =
      candidates.find((element) => element.getClientRects().length > 0) ??
      candidates[0];
    focusTarget?.focus();
  }, []);

  useEffect(() => {
    const mappingId = pendingErrorFocusRef.current;
    if (
      mappingId === null ||
      (!mutationFailures.has(mappingId) &&
        !statusRefreshFailures.has(mappingId))
    ) {
      return;
    }
    pendingErrorFocusRef.current = null;
    focusMutationError(mappingId);
  }, [focusMutationError, mutationFailures, statusRefreshFailures]);

  const startImport = useCallback(
    async (
      item: AdminPublishedMappingImportResponse,
      trigger: HTMLButtonElement | null,
    ) => {
      const activePending = pendingRef.current.get(item.mapping_id);
      if (
        !isStartAction(item.action) ||
        activePending?.authorityIdentity === authorityIdentity
      ) {
        return;
      }
      const requestToken = Symbol(item.mapping_id);
      const controller = new AbortController();
      pendingRef.current.set(item.mapping_id, {
        authorityIdentity,
        controller,
        requestToken,
      });
      setPendingMappings(
        new Set(
          [...pendingRef.current]
            .filter(
              ([, pending]) => pending.authorityIdentity === authorityIdentity,
            )
            .map(([mappingId]) => mappingId),
        ),
      );
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
      const isCurrentRequest = () =>
        hasLivePublishedAuthority(
          authorityIdentityRef.current,
          authorityIdentity,
          ownsPublishedRequestToken(
            pendingRef.current.get(item.mapping_id)?.requestToken,
            requestToken,
          ) &&
            ownsLiveMutationController(
              pendingRef.current.get(item.mapping_id)?.controller ?? null,
              controller,
            ),
        );
      try {
        const result = await startAdminPublishedMappingImport({
          auth: accessToken,
          path: { mapping_id: item.mapping_id, product_id: productId },
          signal: controller.signal,
        });
        if (!isCurrentRequest()) {
          return;
        }
        if (result.data === undefined) {
          throw new Error("import unavailable");
        }
        accepted = true;
        const acceptedImport = result.data;
        initiatedImportsRef.current.set(item.mapping_id, {
          identity: importPollingIdentity(productId, acceptedImport),
          trigger,
        });
        setItems((current) =>
          current.map((previous) =>
            previous.mapping_id === item.mapping_id
              ? preserveNewerImport(previous, acceptedImport)
              : previous,
          ),
        );
        toast.success(t("Import started"));
        const refreshed = await loadCompleteCollection(true);
        if (!refreshed) {
          throw new Error("import status unavailable");
        }
      } catch {
        if (!isCurrentRequest()) {
          return;
        }
        const setFailure = accepted
          ? setStatusRefreshFailures
          : setMutationFailures;
        pendingErrorFocusRef.current = item.mapping_id;
        setFailure((current) => {
          const next = new Set(current);
          next.add(item.mapping_id);
          return next;
        });
      } finally {
        const shouldFinalizePendingState = isCurrentRequest();
        if (
          ownsPublishedRequestToken(
            pendingRef.current.get(item.mapping_id)?.requestToken,
            requestToken,
          )
        ) {
          pendingRef.current.delete(item.mapping_id);
        }
        if (shouldFinalizePendingState) {
          setPendingMappings(
            new Set(
              [...pendingRef.current]
                .filter(
                  ([, pending]) =>
                    pending.authorityIdentity === authorityIdentity,
                )
                .map(([mappingId]) => mappingId),
            ),
          );
        }
      }
    },
    [accessToken, authorityIdentity, loadCompleteCollection, productId],
  );

  const autoStartedRef = useRef(new Set<string>());
  useEffect(() => {
    if (!autoStart || collectionState !== "ready" || pendingMappings.size > 0)
      return;
    let cancelled = false;
    queueMicrotask(() => {
      if (cancelled || loadedAuthorityRef.current !== authorityIdentity) return;
      const item = items.find(
        (item) =>
          item.action === "run_import" &&
          item.state === "not_imported" &&
          !autoStartedRef.current.has(
            JSON.stringify([
              authorityIdentity,
              item.active_revision_id,
              item.mapping_id,
            ]),
          ),
      );
      if (item === undefined) return;
      autoStartedRef.current.add(
        JSON.stringify([
          authorityIdentity,
          item.active_revision_id,
          item.mapping_id,
        ]),
      );
      void startImport(item, null);
    });
    return () => {
      cancelled = true;
    };
  }, [
    autoStart,
    authorityIdentity,
    collectionState,
    items,
    pendingMappings,
    startImport,
  ]);

  const Heading = headingLevel as ElementType;

  return (
    <section className="grid min-w-0 max-w-full gap-4 overflow-x-clip">
      <div className="grid gap-2">
        <Heading className="text-heading font-semibold">
          {autoStart
            ? t("Import progress")
            : compact
              ? t("Imports from published sources")
              : t("Published mapping imports")}
        </Heading>
        <p className="text-muted-foreground">
          {autoStart
            ? t(
                "New sources start importing automatically. You can follow their progress here.",
              )
            : t("Import localization sources from the exact published branch.")}
        </p>
      </div>

      {collectionState === "loading" ? (
        <div className="grid gap-3" role="status" aria-live="polite">
          <Skeleton
            data-testid="published-import-skeleton"
            className="h-24 w-full"
          />
          <span>{t("Loading published mappings")}</span>
        </div>
      ) : null}

      {collectionState === "error" ? (
        <Alert variant="destructive">
          <AlertTitle>
            <h4>{t("Published imports unavailable")}</h4>
          </AlertTitle>
          <AlertDescription>
            <Button
              type="button"
              variant="outline"
              className="min-h-11 whitespace-normal"
              onClick={() => void loadCompleteCollection()}
            >
              {t("Retry loading published imports")}
            </Button>
          </AlertDescription>
        </Alert>
      ) : null}

      {collectionState === "ready" && items.length === 0 ? (
        <div className="grid gap-2 rounded-lg border bg-secondary p-6">
          <h4 className="font-semibold">
            {t("No published mappings to import")}
          </h4>
          <p className="text-muted-foreground">
            {t("Publish a validated mapping before running an import.")}
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

          <Tabs defaultValue="progress" className="min-w-0 max-w-full">
            <TabsList
              aria-label={t("Import views")}
              className="h-auto w-full flex-wrap justify-start"
            >
              <TabsTrigger value="progress">{t("Import progress")}</TabsTrigger>
              <TabsTrigger value="warnings">
                {t("Warnings (")}
                {warningItems.length})
              </TabsTrigger>
              <TabsTrigger value="strings">{t("Imported strings")}</TabsTrigger>
            </TabsList>
            <TabsContent value="progress" className="mt-3">
              <div className="grid gap-3 lg:grid-cols-2">
                {visibleImportRecords
                  .filter((item) => !compact || isImportActive(item))
                  .map((item) => (
                    <ImportProgress
                      key={item.mapping_id}
                      item={item}
                      repositories={repositories}
                    />
                  ))}
              </div>
              {importedMappingCount > 0 ? (
                <Button asChild className="mt-3 w-fit">
                  <Link
                    to={`/products/${encodeURIComponent(productId)}/strings`}
                  >
                    {t("Manage imported strings")}
                  </Link>
                </Button>
              ) : null}
            </TabsContent>
            <TabsContent value="warnings" className="mt-3">
              {warningItems.length === 0 ? (
                <div role="status" className="rounded-lg border bg-card p-4">
                  {t("No import warnings detected.")}
                </div>
              ) : (
                <div className="grid gap-3">
                  {warningItems.map((item) => {
                    const parserWarnings = parserWarningCount(item);
                    const duplicates = item.duplicate_report_summary;
                    const primarySide = item.repository_sides[0];
                    return (
                      <article
                        key={item.mapping_id}
                        className="grid min-w-0 gap-3 rounded-lg border bg-card p-4"
                      >
                        <div className="flex min-w-0 flex-wrap items-center justify-between gap-2">
                          <div className="grid min-w-0 gap-1">
                            <h3 className="font-semibold [overflow-wrap:anywhere]">
                              {primarySide
                                ? repositoryLabel(
                                    primarySide.repository_id,
                                    repositories,
                                  )
                                : t("Published mapping")}
                            </h3>
                            {primarySide ? (
                              <span className="font-mono text-sm [overflow-wrap:anywhere]">
                                {primarySide.source_branch}
                              </span>
                            ) : null}
                          </div>
                          <Badge variant="outline">
                            {STATUS_LABELS[item.state]}
                          </Badge>
                        </div>
                        {duplicates && duplicates.group_count > 0 ? (
                          <p>
                            {duplicates.group_count}{" "}
                            {t(" duplicate key groups ·")}{" "}
                            {duplicates.repeated_occurrences}{" "}
                            {t(" repeated occurrences")}
                          </p>
                        ) : null}
                        {parserWarnings > 0 ? (
                          <div className="grid gap-2">
                            <p>
                              {parserWarnings}{" "}
                              {parserWarnings === 1
                                ? t("parser warning")
                                : t("parser warnings")}
                            </p>
                            <ParserIssues item={item} productId={productId} />
                          </div>
                        ) : null}
                        {item.id !== null &&
                        item.execution_number !== null &&
                        duplicates !== null &&
                        duplicates !== undefined &&
                        duplicates.group_count > 0 ? (
                          <AdminDuplicateAction
                            accessToken={accessToken}
                            productId={productId}
                            item={item}
                          />
                        ) : null}
                      </article>
                    );
                  })}
                </div>
              )}
            </TabsContent>
            <TabsContent value="strings" className="mt-3">
              <div className="grid gap-3 rounded-lg border bg-card p-4">
                {importedMappingCount > 0 ? (
                  <>
                    <p>
                      {t("Imported strings from ")}
                      {importedMappingCount} {t(" published")}{" "}
                      {importedMappingCount === 1
                        ? t("mapping is")
                        : t("mappings are")}{" "}
                      {t("available.")}
                    </p>
                    <Button asChild className="w-fit">
                      <Link
                        to={`/translations?product_id=${encodeURIComponent(productId)}`}
                      >
                        {t("View imported strings")}
                      </Link>
                    </Button>
                  </>
                ) : (
                  <p role="status">
                    {t(
                      "No imported strings yet. Start an import and this view will update automatically.",
                    )}
                  </p>
                )}
              </div>
            </TabsContent>
          </Tabs>

          <div className="hidden max-w-full overflow-x-auto md:block">
            <Table aria-label={t("Published mapping imports")}>
              <TableHeader>
                <TableRow>
                  <TableHead>{t("Mapping")}</TableHead>
                  <TableHead>{t("Import status")}</TableHead>
                  <TableHead>{t("Last successful baseline")}</TableHead>
                  <TableHead>{t("Latest execution")}</TableHead>
                  <TableHead>{t("Actions")}</TableHead>
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
                            productId={productId}
                            focusRef={(element) =>
                              setMutationErrorRef(
                                "desktop",
                                item.mapping_id,
                                element,
                              )
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
                            accessToken={accessToken}
                            productId={productId}
                            automaticUpdatesPaused={automaticUpdatesPaused}
                            item={item}
                            onAction={(triggerElement) => {
                              if (item.action === "review_baseline_change") {
                                onReviewBaselineChange?.(item);
                                setRewriteReview({
                                  importRecord: item,
                                  triggerElement,
                                });
                              } else {
                                void startImport(item, triggerElement);
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
            aria-label={t("Published mapping imports mobile list")}
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
                    <span className="text-sm font-semibold">
                      {t("Mapping")}
                    </span>
                    <RepositorySides item={item} repositories={repositories} />
                  </div>
                  <div className="grid gap-1">
                    <span className="text-sm font-semibold">
                      {t("Import status")}
                    </span>
                    <Badge className="w-fit" variant="outline">
                      {STATUS_LABELS[item.state]}
                    </Badge>
                  </div>
                  <div className="grid min-w-0 gap-1">
                    <span className="text-sm font-semibold">
                      {t("Last successful baseline")}
                    </span>
                    <Baseline item={item} />
                  </div>
                  <div className="grid gap-1">
                    <span className="text-sm font-semibold">
                      {t("Latest execution")}
                    </span>
                    <LatestExecution item={item} />
                  </div>
                  <RowError
                    productId={productId}
                    focusRef={(element) =>
                      setMutationErrorRef("mobile", item.mapping_id, element)
                    }
                    item={item}
                    mutationFailed={mutationFailures.has(item.mapping_id)}
                    pollingFailed={
                      pollingError || statusRefreshFailures.has(item.mapping_id)
                    }
                  />
                  <ImportAction
                    accessToken={accessToken}
                    productId={productId}
                    automaticUpdatesPaused={automaticUpdatesPaused}
                    item={item}
                    onAction={(triggerElement) => {
                      if (item.action === "review_baseline_change") {
                        onReviewBaselineChange?.(item);
                        setRewriteReview({
                          importRecord: item,
                          triggerElement,
                        });
                      } else {
                        void startImport(item, triggerElement);
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
            {t(announcement)}
          </p>

          {rewriteReview !== null ? (
            <RewrittenBaselineDialog
              accessToken={accessToken}
              importRecord={rewriteReview.importRecord}
              onClose={() => setRewriteReview(null)}
              onConfirmed={async () => {
                const refreshed = await loadCompleteCollection(true);
                if (refreshed) setAnnouncement(t("Baseline updated"));
                return refreshed;
              }}
              open
              productId={productId}
              repositories={repositories}
              triggerElement={rewriteReview.triggerElement}
            />
          ) : null}
        </>
      ) : null}
    </section>
  );
}
