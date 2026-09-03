import { useCallback, useEffect, useMemo, useRef, useState } from "react";
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

const SIDE_LABELS = {
  direct: "Source",
  keys: "Keys",
  translations: "Translations",
} as const;

const CHANGE_LABELS = {
  added: "Added",
  modified: "Modified",
  removed: "Removed",
} as const;

type ComparisonLoadState =
  | { status: "loading" }
  | { status: "error" }
  | { comparison: AdminImportRewriteComparisonResponse; status: "ready" };

type ConfirmationError = "generic" | "stale" | null;

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
              aria-label="Copy full commit"
              onClick={() => void copyCommit()}
            >
              <Copy aria-hidden="true" />
            </Button>
          </TooltipTrigger>
          <TooltipContent>Copy full commit</TooltipContent>
        </Tooltip>
      </TooltipProvider>
      {copied ? (
        <span className="sr-only" role="status" aria-live="polite">
          Full commit copied
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
  const label = SIDE_LABELS[side.repository_side];
  return (
    <section
      aria-label={`${label} baseline comparison`}
      className="grid min-w-0 gap-4 rounded-lg border p-4"
    >
      <h3 className="text-heading font-semibold">{label}</h3>
      <dl className="grid min-w-0 gap-3">
        <div className="grid min-w-0 gap-1">
          <dt className="text-sm font-semibold">Repository</dt>
          <dd className="[overflow-wrap:anywhere]">
            {repositoryLabel(side.repository_id, repositories)}
          </dd>
        </div>
        <div className="grid min-w-0 gap-1">
          <dt className="text-sm font-semibold">Branch</dt>
          <dd className="font-mono [overflow-wrap:anywhere]">
            {sideBranch(side, importRecord)}
          </dd>
        </div>
        <div className="grid min-w-0 gap-1">
          <dt className="text-sm font-semibold">Current baseline</dt>
          <dd className="min-w-0">
            <FullCommit commit={side.old_commit_hash} />
          </dd>
        </div>
        <div className="grid min-w-0 gap-1">
          <dt className="text-sm font-semibold">Proposed baseline</dt>
          <dd className="min-w-0">
            <FullCommit commit={side.new_commit_hash} />
          </dd>
        </div>
      </dl>
      <div
        aria-label={`${label} change summary`}
        className="flex flex-wrap gap-2"
      >
        <Badge variant="outline">Added {side.added_count}</Badge>
        <Badge variant="outline">Modified {side.modified_count}</Badge>
        <Badge variant="outline">Removed {side.removed_count}</Badge>
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
  const requestGenerationRef = useRef(0);
  const controllerRef = useRef<AbortController | null>(null);
  const confirmationPendingRef = useRef(false);
  const errorRef = useRef<HTMLDivElement>(null);
  const [loadState, setLoadState] = useState<ComparisonLoadState>({
    status: "loading",
  });
  const [confirmationPending, setConfirmationPending] = useState(false);
  const [confirmationError, setConfirmationError] =
    useState<ConfirmationError>(null);

  const importIdentity = useMemo(
    () =>
      JSON.stringify({
        id: importRecord.id,
        mappingId: importRecord.mapping_id,
        productId,
        repositorySides: importRecord.repository_sides,
        topology: importRecord.topology,
      }),
    [importRecord, productId],
  );

  const restoreTriggerFocus = useCallback(() => {
    queueMicrotask(() => triggerElement?.focus());
  }, [triggerElement]);

  const finishClose = useCallback(() => {
    requestGenerationRef.current += 1;
    controllerRef.current?.abort();
    onClose();
    restoreTriggerFocus();
  }, [onClose, restoreTriggerFocus]);

  const requestClose = useCallback(
    (nextOpen: boolean) => {
      if (nextOpen || confirmationPendingRef.current) {
        return;
      }
      finishClose();
    },
    [finishClose],
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
    if (confirmationPendingRef.current || importRecord.id === null) {
      return;
    }
    const expectedIdentity = importIdentity;
    confirmationPendingRef.current = true;
    setConfirmationPending(true);
    setConfirmationError(null);
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
      });
      if (expectedIdentity !== importIdentity) {
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
      const refreshed = await onConfirmed(result.data);
      if (expectedIdentity !== importIdentity) {
        return;
      }
      if (!refreshed) {
        setConfirmationError("generic");
        return;
      }
      toast.success("Baseline updated");
      confirmationPendingRef.current = false;
      setConfirmationPending(false);
      finishClose();
    } catch {
      if (expectedIdentity === importIdentity) {
        setConfirmationError("generic");
      }
    } finally {
      confirmationPendingRef.current = false;
      setConfirmationPending(false);
    }
  }

  return (
    <AlertDialog open={open} onOpenChange={requestClose}>
      <AlertDialogContent
        className="max-h-[80vh] min-w-0 max-w-3xl grid-rows-[auto_minmax(0,1fr)_auto] overflow-hidden sm:max-w-3xl"
        onEscapeKeyDown={(event) => {
          if (confirmationPendingRef.current) event.preventDefault();
        }}
      >
        <AlertDialogHeader>
          <AlertDialogTitle>Review rewritten source history</AlertDialogTitle>
          <AlertDialogDescription>
            This branch no longer descends from the last successful baseline.
            Review the complete localization-file change before choosing a new
            baseline.
          </AlertDialogDescription>
        </AlertDialogHeader>

        <div
          role="region"
          aria-label="Rewritten baseline comparison content"
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
              <span>Loading baseline comparison</span>
            </div>
          ) : null}

          {loadState.status === "error" ? (
            <Alert ref={errorRef} tabIndex={-1} variant="destructive">
              <AlertTitle>Baseline comparison unavailable</AlertTitle>
              <AlertDescription>
                The proposed source could not be read safely. Close this review
                and retry the import later.
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
                <p>No localization file changes detected</p>
              ) : (
                <div
                  role="region"
                  aria-label="Localization file changes scroll area"
                  // eslint-disable-next-line jsx-a11y/no-noninteractive-tabindex
                  tabIndex={0}
                  className="max-w-full overflow-x-auto rounded-md outline-none focus-visible:ring-2 focus-visible:ring-ring"
                >
                  <Table aria-label="Localization file changes">
                    <TableHeader>
                      <TableRow>
                        <TableHead>Change</TableHead>
                        <TableHead>Repository side</TableHead>
                        <TableHead>File path</TableHead>
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
                  Use the rewritten baseline?
                </h3>
                <p className="text-sm text-muted-foreground">
                  The proposed commits will replace the current baseline for
                  this mapping. Pending edits remain tied to the old baseline
                  and cannot be submitted until they are reapplied or
                  reconciled.
                </p>
              </section>

              {confirmationError !== null ? (
                <Alert ref={errorRef} tabIndex={-1} variant="destructive">
                  <AlertTitle>
                    {confirmationError === "stale"
                      ? "Baseline changed again"
                      : "Baseline update unavailable"}
                  </AlertTitle>
                  <AlertDescription>
                    {confirmationError === "stale"
                      ? "The proposed baseline is no longer current. Close this review and run the import again."
                      : "The baseline could not be updated safely. Close this review and run the import again."}
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
            Keep current baseline
          </AlertDialogCancel>
          {loadState.status === "ready" ? (
            <Button
              type="button"
              className="min-h-[44px]"
              disabled={confirmationPending}
              aria-busy={confirmationPending}
              onClick={() => void confirmBaseline(loadState.comparison)}
            >
              Confirm new baseline
            </Button>
          ) : null}
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
