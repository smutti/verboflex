import { t, useUiLanguage } from "@/i18n";
import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { Copy } from "lucide-react";
import { toast } from "sonner";

import {
  confirmAdminImportRewriteBaseline,
  getAdminImportRewriteComparison,
  type AdminImportRewriteComparisonResponse,
  type AdminImportRewriteSideResponse,
  type AdminPublishedMappingImportResponse,
  type AdminRepositoryResponse,
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
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "../../../components/ui/table";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "../../../components/ui/tooltip";
import {
  isLiveRewriteConfirmationRequest,
  ownsLiveMutationController,
  shouldClearUncommittedConfirmation,
} from "./mutationAuthority";

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

const CHANGE_LABELS = {
  get added() {
    return t("Added");
  },
  get modified() {
    return t("Modified");
  },
  get removed() {
    return t("Removed");
  },
} as const;

type ComparisonLoadState =
  | { status: "loading" }
  | { status: "error" }
  | { comparison: AdminImportRewriteComparisonResponse; status: "ready" };

type ConfirmationError = "generic" | "stale" | null;
type ConfirmationProgress = {
  identity: string;
  status: "committed" | "pending";
} | null;

export interface RewrittenBaselineDialogProps {
  accessToken: string;
  importRecord: AdminPublishedMappingImportResponse;
  onClose: () => void;
  onConfirmed: (
    importRecord: AdminPublishedMappingImportResponse,
  ) => boolean | Promise<boolean>;
  open: boolean;
  productId: string;
  repositories?: readonly AdminRepositoryResponse[];
  triggerElement: HTMLButtonElement | null;
}

function comparisonMatchesImport(
  comparison: AdminImportRewriteComparisonResponse,
  importRecord: AdminPublishedMappingImportResponse,
) {
  if (
    importRecord.id === null ||
    comparison.confirmable !== true ||
    comparison.import_id !== importRecord.id ||
    comparison.mapping_id !== importRecord.mapping_id ||
    comparison.topology !== importRecord.topology ||
    comparison.sides.length !== importRecord.repository_sides.length
  ) {
    return false;
  }
  return comparison.sides.every((side, index) => {
    const expected = importRecord.repository_sides[index];
    return (
      expected !== undefined &&
      side.repository_side === expected.role &&
      side.repository_id === expected.repository_id
    );
  });
}

function repositoryLabel(
  repositoryId: string,
  repositories: readonly AdminRepositoryResponse[],
) {
  const repository = repositories.find((item) => item.id === repositoryId);
  return (
    repository?.descriptive_name ??
    (repository === undefined
      ? repositoryId
      : `${repository.workspace}/${repository.repository_slug}`)
  );
}

function sideBranch(
  side: AdminImportRewriteSideResponse,
  importRecord: AdminPublishedMappingImportResponse,
) {
  return importRecord.repository_sides.find(
    (candidate) =>
      candidate.role === side.repository_side &&
      candidate.repository_id === side.repository_id,
  )!.source_branch;
}

function FullCommit({ commit }: { commit: string }) {
  useUiLanguage();
  const [copied, setCopied] = useState(false);

  async function copyCommit() {
    try {
      await navigator.clipboard.writeText(commit);
      setCopied(true);
    } catch {
      setCopied(false);
    }
  }

  return (
    <div className="flex min-w-0 items-start gap-2">
      <code className="min-w-0 flex-1 font-mono text-sm [overflow-wrap:anywhere]">
        {commit}
      </code>
      <TooltipProvider>
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              type="button"
              variant="outline"
              size="icon"
              className="min-h-[44px] min-w-[44px] shrink-0"
              aria-label={t("Copy full commit")}
              onClick={() => void copyCommit()}
            >
              <Copy aria-hidden="true" />
            </Button>
          </TooltipTrigger>
          <TooltipContent>{t("Copy full commit")}</TooltipContent>
        </Tooltip>
      </TooltipProvider>
      {copied ? (
        <span className="sr-only" role="status" aria-live="polite">
          {t("Full commit copied")}
        </span>
      ) : null}
    </div>
  );
}

function SideComparison({
  importRecord,
  repositories,
  side,
}: {
  importRecord: AdminPublishedMappingImportResponse;
  repositories: readonly AdminRepositoryResponse[];
  side: AdminImportRewriteSideResponse;
}) {
  useUiLanguage();
  const label = SIDE_LABELS[side.repository_side];
  return (
    <section
      aria-label={t("{{v0}} baseline comparison", { v0: label })}
      className="grid min-w-0 gap-4 rounded-lg border p-4"
    >
      <h3 className="text-heading font-semibold">{label}</h3>
      <dl className="grid min-w-0 gap-3">
        <div className="grid min-w-0 gap-1">
          <dt className="text-sm font-semibold">{t("Repository")}</dt>
          <dd className="[overflow-wrap:anywhere]">
            {repositoryLabel(side.repository_id, repositories)}
          </dd>
        </div>
        <div className="grid min-w-0 gap-1">
          <dt className="text-sm font-semibold">{t("Branch")}</dt>
          <dd className="font-mono [overflow-wrap:anywhere]">
            {sideBranch(side, importRecord)}
          </dd>
        </div>
        <div className="grid min-w-0 gap-1">
          <dt className="text-sm font-semibold">{t("Current baseline")}</dt>
          <dd className="min-w-0">
            <FullCommit commit={side.old_commit_hash} />
          </dd>
        </div>
        <div className="grid min-w-0 gap-1">
          <dt className="text-sm font-semibold">{t("Proposed baseline")}</dt>
          <dd className="min-w-0">
            <FullCommit commit={side.new_commit_hash} />
          </dd>
        </div>
      </dl>
      <div
        aria-label={t("{{v0}} change summary", { v0: label })}
        className="flex flex-wrap gap-2"
      >
        <Badge variant="outline">
          {t("Added ")}
          {side.added_count}
        </Badge>
        <Badge variant="outline">
          {t("Modified ")}
          {side.modified_count}
        </Badge>
        <Badge variant="outline">
          {t("Removed ")}
          {side.removed_count}
        </Badge>
      </div>
    </section>
  );
}

export function RewrittenBaselineDialog({
  accessToken,
  importRecord,
  onClose,
  onConfirmed,
  open,
  productId,
  repositories = [],
  triggerElement,
}: RewrittenBaselineDialogProps) {
  useUiLanguage();
  const requestGenerationRef = useRef(0);
  const controllerRef = useRef<AbortController | null>(null);
  const confirmationControllerRef = useRef<AbortController | null>(null);
  const confirmationRequestRef = useRef<{
    identity: string;
    token: symbol;
  } | null>(null);
  const errorRef = useRef<HTMLDivElement>(null);
  const [loadState, setLoadState] = useState<ComparisonLoadState>({
    status: "loading",
  });
  const [confirmationProgress, setConfirmationProgress] =
    useState<ConfirmationProgress>(null);
  const [confirmationError, setConfirmationError] =
    useState<ConfirmationError>(null);

  const importIdentity = useMemo(
    () =>
      JSON.stringify({
        accessToken,
        id: importRecord.id,
        mappingId: importRecord.mapping_id,
        productId,
        repositorySides: importRecord.repository_sides,
        topology: importRecord.topology,
      }),
    [accessToken, importRecord, productId],
  );
  const importIdentityRef = useRef(importIdentity);
  useLayoutEffect(() => {
    importIdentityRef.current = importIdentity;
  }, [importIdentity]);
  useEffect(
    () => () => {
      confirmationControllerRef.current?.abort();
      confirmationControllerRef.current = null;
      confirmationRequestRef.current = null;
    },
    [importIdentity],
  );
  const confirmationPending =
    confirmationProgress?.identity === importIdentity &&
    confirmationProgress.status === "pending";
  const confirmationCommitted =
    confirmationProgress?.identity === importIdentity &&
    confirmationProgress.status === "committed";

  const restoreTriggerFocus = useCallback(() => {
    queueMicrotask(() => triggerElement?.focus());
  }, [triggerElement]);

  const finishClose = useCallback(() => {
    requestGenerationRef.current += 1;
    controllerRef.current?.abort();
    confirmationControllerRef.current?.abort();
    confirmationControllerRef.current = null;
    confirmationRequestRef.current = null;
    onClose();
    restoreTriggerFocus();
  }, [onClose, restoreTriggerFocus]);

  const requestClose = useCallback(
    (nextOpen: boolean) => {
      if (
        nextOpen ||
        confirmationRequestRef.current?.identity === importIdentity
      ) {
        return;
      }
      finishClose();
    },
    [finishClose, importIdentity],
  );

  useEffect(() => {
    if (!open || importRecord.id === null) {
      return;
    }
    const generation = ++requestGenerationRef.current;
    const expectedIdentity = importIdentity;
    controllerRef.current?.abort();
    const controller = new AbortController();
    controllerRef.current = controller;
    queueMicrotask(() => {
      if (
        controller.signal.aborted ||
        requestGenerationRef.current !== generation
      ) {
        return;
      }
      setLoadState({ status: "loading" });
      setConfirmationError(null);

      void (async () => {
        try {
          const result = await getAdminImportRewriteComparison({
            auth: accessToken,
            path: {
              import_id: importRecord.id!,
              mapping_id: importRecord.mapping_id,
              product_id: productId,
            },
            signal: controller.signal,
          });
          if (
            controller.signal.aborted ||
            requestGenerationRef.current !== generation ||
            expectedIdentity !== importIdentity
          ) {
            return;
          }
          if (
            result.data === undefined ||
            !comparisonMatchesImport(result.data, importRecord)
          ) {
            throw new Error("comparison unavailable");
          }
          setLoadState({ comparison: result.data, status: "ready" });
        } catch {
          if (
            !controller.signal.aborted &&
            requestGenerationRef.current === generation
          ) {
            setLoadState({ status: "error" });
          }
        }
      })();
    });

    return () => controller.abort();
  }, [accessToken, importIdentity, importRecord, open, productId]);

  useEffect(() => {
    if (loadState.status === "error" || confirmationError !== null) {
      errorRef.current?.focus();
    }
  }, [confirmationError, loadState.status]);

  async function confirmBaseline(
    comparison: AdminImportRewriteComparisonResponse,
  ) {
    if (
      confirmationRequestRef.current?.identity === importIdentity ||
      importRecord.id === null
    ) {
      return;
    }
    const expectedIdentity = importIdentity;
    const requestToken = Symbol(importRecord.id);
    confirmationControllerRef.current?.abort();
    const controller = new AbortController();
    confirmationControllerRef.current = controller;
    confirmationRequestRef.current = {
      identity: expectedIdentity,
      token: requestToken,
    };
    setConfirmationProgress({
      identity: expectedIdentity,
      status: "pending",
    });
    setConfirmationError(null);
    let committed = false;
    const isCurrentRequest = () =>
      ownsLiveMutationController(
        confirmationControllerRef.current,
        controller,
      ) &&
      isLiveRewriteConfirmationRequest(
        importIdentityRef.current,
        expectedIdentity,
        confirmationRequestRef.current?.token,
        requestToken,
      );
    try {
      const result = await confirmAdminImportRewriteBaseline({
        auth: accessToken,
        body: {
          proposal_digest: comparison.proposal_digest,
          proposal_id: comparison.proposal_id,
          proposed_execution_id: comparison.proposed_execution_id,
        },
        path: {
          import_id: importRecord.id,
          mapping_id: importRecord.mapping_id,
          product_id: productId,
        },
        signal: controller.signal,
      });
      if (!isCurrentRequest()) {
        return;
      }
      if (result.data === undefined) {
        setConfirmationError(
          result.response?.status === 409 ? "stale" : "generic",
        );
        return;
      }
      if (
        result.data.id !== importRecord.id ||
        result.data.mapping_id !== importRecord.mapping_id
      ) {
        setConfirmationError("stale");
        return;
      }
      committed = true;
      setConfirmationProgress({
        identity: expectedIdentity,
        status: "committed",
      });
      try {
        await onConfirmed(result.data);
      } catch {
        // The provider baseline is already committed; collection refresh is separate.
      }
      if (!isCurrentRequest()) return;
      toast.success(t("Baseline updated"));
      finishClose();
    } catch {
      if (isCurrentRequest()) {
        setConfirmationError("generic");
      }
    } finally {
      const ownsCurrentRequest = isCurrentRequest();
      if (
        confirmationRequestRef.current?.token === requestToken &&
        confirmationControllerRef.current === controller
      ) {
        confirmationRequestRef.current = null;
        confirmationControllerRef.current = null;
      }
      if (
        shouldClearUncommittedConfirmation(
          importIdentityRef.current,
          expectedIdentity,
          ownsCurrentRequest,
          committed,
        )
      ) {
        setConfirmationProgress(null);
      }
    }
  }

  return (
    <AlertDialog open={open} onOpenChange={requestClose}>
      <AlertDialogContent
        className="max-h-[80vh] min-w-0 max-w-3xl grid-rows-[auto_minmax(0,1fr)_auto] overflow-hidden sm:max-w-3xl"
        onEscapeKeyDown={(event) => {
          if (confirmationRequestRef.current?.identity === importIdentity) {
            event.preventDefault();
          }
        }}
      >
        <AlertDialogHeader>
          <AlertDialogTitle>
            {t("Review rewritten source history")}
          </AlertDialogTitle>
          <AlertDialogDescription>
            {t(
              "This branch no longer descends from the last successful baseline. Review the complete localization-file change before choosing a new baseline.",
            )}
          </AlertDialogDescription>
        </AlertDialogHeader>

        <div
          role="region"
          aria-label={t("Rewritten baseline comparison content")}
          // The comparison may contain many metadata rows; scrolling remains local and keyboard accessible.
          // eslint-disable-next-line jsx-a11y/no-noninteractive-tabindex
          tabIndex={0}
          className="grid min-h-0 min-w-0 gap-4 overflow-y-auto overscroll-contain pr-1 outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          {loadState.status === "loading" ? (
            <div className="grid gap-3" role="status" aria-live="polite">
              <Skeleton
                data-testid="rewrite-comparison-skeleton"
                className="h-32 w-full"
              />
              <span>{t("Loading baseline comparison")}</span>
            </div>
          ) : null}

          {loadState.status === "error" ? (
            <Alert ref={errorRef} tabIndex={-1} variant="destructive">
              <AlertTitle>{t("Baseline comparison unavailable")}</AlertTitle>
              <AlertDescription>
                {t(
                  "The proposed source could not be read safely. Close this review and retry the import later.",
                )}
              </AlertDescription>
            </Alert>
          ) : null}

          {loadState.status === "ready" ? (
            <>
              {loadState.comparison.sides.map((side) => (
                <SideComparison
                  key={`${side.repository_side}:${side.repository_id}`}
                  importRecord={importRecord}
                  repositories={repositories}
                  side={side}
                />
              ))}

              {loadState.comparison.files.length === 0 ? (
                <p>{t("No localization file changes detected")}</p>
              ) : (
                <div
                  role="region"
                  aria-label={t("Localization file changes scroll area")}
                  // eslint-disable-next-line jsx-a11y/no-noninteractive-tabindex
                  tabIndex={0}
                  className="max-w-full overflow-x-auto rounded-md outline-none focus-visible:ring-2 focus-visible:ring-ring"
                >
                  <Table aria-label={t("Localization file changes")}>
                    <TableHeader>
                      <TableRow>
                        <TableHead>{t("Change")}</TableHead>
                        <TableHead>{t("Repository side")}</TableHead>
                        <TableHead>{t("File path")}</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {loadState.comparison.files.map((file) => (
                        <TableRow
                          key={`${file.position}:${file.repository_side}:${file.path}`}
                        >
                          <TableCell>
                            <Badge variant="outline">
                              {CHANGE_LABELS[file.change]}
                            </Badge>
                          </TableCell>
                          <TableCell>
                            {SIDE_LABELS[file.repository_side]}
                          </TableCell>
                          <TableCell className="font-mono whitespace-normal [overflow-wrap:anywhere]">
                            {file.path}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              )}

              <section
                className="grid gap-2"
                aria-labelledby="rewrite-confirmation-title"
              >
                <h3 id="rewrite-confirmation-title" className="font-semibold">
                  {t("Use the rewritten baseline?")}
                </h3>
                <p className="text-sm text-muted-foreground">
                  {t(
                    "Pending edits are kept. Edits affected by source changes need reconciliation before submission.",
                  )}
                </p>
              </section>

              {confirmationError !== null ? (
                <Alert ref={errorRef} tabIndex={-1} variant="destructive">
                  <AlertTitle>
                    {confirmationError === "stale"
                      ? t("Baseline changed again")
                      : t("Baseline update unavailable")}
                  </AlertTitle>
                  <AlertDescription>
                    {confirmationError === "stale"
                      ? t(
                          "The proposed baseline is no longer current. Close this review and run the import again.",
                        )
                      : t(
                          "The baseline could not be updated safely. Close this review and run the import again.",
                        )}
                  </AlertDescription>
                </Alert>
              ) : null}
            </>
          ) : null}
        </div>

        <AlertDialogFooter>
          <AlertDialogCancel
            className="min-h-[44px]"
            disabled={confirmationPending}
          >
            {t("Keep current baseline")}
          </AlertDialogCancel>
          {loadState.status === "ready" ? (
            <Button
              type="button"
              className="min-h-[44px]"
              disabled={confirmationPending || confirmationCommitted}
              aria-busy={confirmationPending}
              onClick={() => void confirmBaseline(loadState.comparison)}
            >
              {t("Confirm new baseline")}
            </Button>
          ) : null}
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
