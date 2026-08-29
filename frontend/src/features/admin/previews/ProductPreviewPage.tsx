import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { useParams } from "react-router-dom";
import { toast } from "sonner";

import {
  confirmAdminPreviewJob,
  createAdminPreviewJob,
  getAdminProduct,
  listAdminRevisionMappings,
  listAdminRepositoryBranches,
  publishAdminProductCandidate,
  reactivateAdminProduct,
  type AdminMappingResponse,
  type AdminPreviewCommitRequest,
  type AdminPreviewJobResponse,
  type AdminPreviewLayoutCandidateResponse,
  type AdminProductResponse,
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
import { RadioGroup, RadioGroupItem } from "../../../components/ui/radio-group";
import { Skeleton } from "../../../components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "../../../components/ui/table";
import { previewJobIdentity, usePreviewPolling } from "./usePreviewPolling";

export interface ProductPreviewPageProps {
  accessToken: string;
  productId?: string;
}

type PageState =
  | { status: "loading" }
  | { status: "error" }
  | {
      status: "ready";
      mappings: AdminMappingResponse[];
      product: AdminProductResponse;
      productId: string;
    };

type PublicationBlocker =
  | "layout_required"
  | "mapping_configuration_invalid"
  | "mappings_required"
  | "preview_confirmation_required"
  | "target_configuration_invalid";

const JOB_LABELS: Record<AdminPreviewJobResponse["state"], string> = {
  failed: "Failed",
  queued: "Queued",
  running: "Running",
  succeeded: "Succeeded",
  timed_out: "Timed out",
};

const FORMAT_LABELS: Record<
  AdminPreviewLayoutCandidateResponse["format"],
  string
> = {
  android_xml: "Android XML",
  ios_strings: "iOS strings",
  json: "JSON",
  qt_ts: "Qt TS",
};

const BLOCKER_LABELS: Record<PublicationBlocker, string> = {
  layout_required: "Layout selection required",
  mapping_configuration_invalid: "Mapping configuration invalid",
  mappings_required: "At least one mapping is required",
  preview_confirmation_required: "Preview confirmation required",
  target_configuration_invalid: "Target configuration invalid",
};

function candidateLabel(candidate: AdminPreviewLayoutCandidateResponse) {
  return `${FORMAT_LABELS[candidate.format]} — ${candidate.layout_identity}`;
}

function isExactCandidate(candidate: AdminPreviewLayoutCandidateResponse) {
  return (
    candidate.confidence === 1 &&
    candidate.files.length > 0 &&
    candidate.languages.length > 0 &&
    candidate.keys.length > 0 &&
    candidate.samples.length > 0
  );
}

function responseStatus(result: { response?: Response }) {
  return result.response?.status;
}

function publicationBlockers(error: unknown): PublicationBlocker[] {
  if (typeof error !== "object" || error === null || !("blockers" in error)) {
    return [];
  }
  const blockers = error.blockers;
  if (!Array.isArray(blockers)) {
    return [];
  }
  return blockers.filter(
    (blocker): blocker is PublicationBlocker =>
      blocker === "layout_required" ||
      blocker === "mapping_configuration_invalid" ||
      blocker === "mappings_required" ||
      blocker === "preview_confirmation_required" ||
      blocker === "target_configuration_invalid",
  );
}

function hasPublishedPreviewConfirmation(mapping: AdminMappingResponse) {
  return (
    mapping.selected_layout_candidate_id !== null &&
    mapping.selected_layout_version !== null
  );
}

async function resolveCommits(
  accessToken: string,
  mapping: AdminMappingResponse,
) {
  const sides: Array<{
    branch: string;
    repositoryId: string;
    role: AdminPreviewCommitRequest["role"];
  }> =
    mapping.topology === "direct"
      ? [
          {
            branch: mapping.primary_source_branch,
            repositoryId: mapping.primary_repository_id,
            role: "direct",
          },
        ]
      : [
          {
            branch: mapping.primary_source_branch,
            repositoryId: mapping.primary_repository_id,
            role: "keys",
          },
          {
            branch: mapping.translations_source_branch ?? "",
            repositoryId: mapping.translations_repository_id ?? "",
            role: "translations",
          },
        ];

  return Promise.all(
    sides.map(async (side): Promise<AdminPreviewCommitRequest> => {
      if (side.branch === "" || side.repositoryId === "") {
        throw new Error();
      }
      const result = await listAdminRepositoryBranches({
        auth: accessToken,
        path: { repository_id: side.repositoryId },
        query: { cursor: null, limit: 100 },
      });
      const branch = result.data?.items.find(
        (item) => item.name === side.branch,
      );
      if (branch === undefined) {
        throw new Error();
      }
      return { commit_hash: branch.commit_hash, role: side.role };
    }),
  );
}

function PreviewAlert({
  children,
  title,
}: {
  children: ReactNode;
  title: string;
}) {
  return (
    <Alert variant="destructive">
      <AlertTitle>{title}</AlertTitle>
      <AlertDescription>{children}</AlertDescription>
    </Alert>
  );
}

function CandidateDetails({
  candidate,
  job,
}: {
  candidate: AdminPreviewLayoutCandidateResponse;
  job: AdminPreviewJobResponse;
}) {
  const side = job.repository_sides.find(
    (repositorySide) => repositorySide.role === candidate.repository_side,
  );
  const commit = side?.commit_hash ?? "";

  return (
    <section
      aria-label="Selected layout preview"
      className="grid min-w-0 gap-6 rounded-lg border bg-secondary p-6"
    >
      <h3 className="text-heading font-semibold">Selected layout</h3>
      <dl className="grid gap-3 sm:grid-cols-2">
        <div>
          <dt className="text-muted-foreground">Repository side</dt>
          <dd className="capitalize">{candidate.repository_side}</dd>
        </div>
        <div>
          <dt className="text-muted-foreground">Branch</dt>
          <dd className="break-all font-mono">{side?.source_branch}</dd>
        </div>
        <div>
          <dt className="text-muted-foreground">Format</dt>
          <dd>{FORMAT_LABELS[candidate.format]}</dd>
        </div>
        <div>
          <dt className="text-muted-foreground">Layout</dt>
          <dd className="break-all font-mono">{candidate.layout_identity}</dd>
        </div>
        <div className="sm:col-span-2">
          <dt className="text-muted-foreground">Commit</dt>
          <dd className="flex flex-wrap items-center gap-3 font-mono">
            <span>{commit.slice(0, 12)}</span>
            <Button
              type="button"
              variant="outline"
              aria-label="Copy full commit"
              onClick={() => void navigator.clipboard?.writeText(commit)}
            >
              Copy full commit
            </Button>
          </dd>
        </div>
      </dl>

      <div
        role="region"
        aria-label="Detected preview files"
        // Exact provider paths may be wider than the page and remain locally focusable.
        // eslint-disable-next-line jsx-a11y/no-noninteractive-tabindex
        tabIndex={0}
        className="max-w-full overflow-x-auto rounded-md outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <div className="w-max min-w-full space-y-2">
          <p>
            <span className="font-medium">Files: </span>
            {candidate.files.join(", ")}
          </p>
          <p>
            <span className="font-medium">Languages: </span>
            {candidate.languages.join(", ")}
          </p>
          <p>
            <span className="font-medium">Keys: </span>
            {candidate.keys.join(", ")}
          </p>
        </div>
      </div>

      <p className="font-medium">
        Preview samples are partial: up to 10 per language and 100 total.
      </p>
      <div
        role="region"
        aria-label="Partial sample overflow"
        // Bounded translations can still be long and use local keyboard overflow.
        // eslint-disable-next-line jsx-a11y/no-noninteractive-tabindex
        tabIndex={0}
        className="max-w-full overflow-x-auto rounded-md outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <Table aria-label="Partial translation samples" className="min-w-2xl">
          <TableHeader>
            <TableRow>
              <TableHead>Language</TableHead>
              <TableHead>Key</TableHead>
              <TableHead>Translation</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {candidate.samples.map((sample, index) => (
              <TableRow key={`${sample.language}-${sample.key}-${index}`}>
                <TableCell>{sample.language}</TableCell>
                <TableCell className="font-mono">{sample.key}</TableCell>
                <TableCell>{sample.translation}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </section>
  );
}

function PreviewJobView({
  accessToken,
  initialJob,
  onConfirmed,
  onRetry,
}: {
  accessToken: string;
  initialJob: AdminPreviewJobResponse;
  onConfirmed: (confirmed: boolean) => void;
  onRetry: () => void;
}) {
  const [announcement, setAnnouncement] = useState("");
  const [selectedCandidateId, setSelectedCandidateId] = useState("");
  const [confirmPending, setConfirmPending] = useState(false);
  const confirmPendingRef = useRef(false);
  const [confirmError, setConfirmError] = useState(false);
  const [confirmedIdentity, setConfirmedIdentity] = useState<string | null>(
    null,
  );
  const { automaticUpdatesPaused, job, pollingError, refreshStatus } =
    usePreviewPolling({
      accessToken,
      initialJob,
      onAnnouncement: setAnnouncement,
    });

  const result = job.result;
  const candidates = result?.layout_candidates ?? [];
  const candidatesAreExact =
    candidates.length > 0 && candidates.every(isExactCandidate);
  const confirmable =
    job.state === "succeeded" &&
    job.is_current &&
    result !== null &&
    candidatesAreExact;
  const selectedCandidate = candidates.find(
    (candidate) => candidate.id === selectedCandidateId,
  );
  const currentConfirmationIdentity =
    result === null || selectedCandidate === undefined
      ? null
      : `${previewJobIdentity(job)}:${result.digest}:${selectedCandidate.id}`;
  const confirmed =
    currentConfirmationIdentity !== null &&
    confirmedIdentity === currentConfirmationIdentity;

  useEffect(() => {
    if (!confirmed) {
      onConfirmed(false);
    }
  }, [confirmed, onConfirmed]);

  async function submitConfirmation() {
    if (
      confirmPendingRef.current ||
      !confirmable ||
      selectedCandidate === undefined ||
      result === null ||
      currentConfirmationIdentity === null
    ) {
      return;
    }
    confirmPendingRef.current = true;
    setConfirmPending(true);
    setConfirmError(false);
    try {
      const response = await confirmAdminPreviewJob({
        auth: accessToken,
        body: {
          layout_candidate_id: selectedCandidate.id,
          layout_candidate_version: selectedCandidate.version,
          preview_digest: result.digest,
        },
        path: { job_id: job.id },
      });
      if (response.data === undefined) {
        setConfirmError(true);
        return;
      }
      setConfirmedIdentity(currentConfirmationIdentity);
      onConfirmed(true);
    } catch {
      setConfirmError(true);
    } finally {
      confirmPendingRef.current = false;
      setConfirmPending(false);
    }
  }

  return (
    <div className="grid gap-6">
      <div aria-live="polite" aria-atomic="true" className="sr-only">
        {announcement}
      </div>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Badge variant="outline" className="w-fit rounded-md">
          {JOB_LABELS[job.state]}
        </Badge>
        {automaticUpdatesPaused &&
        job.state !== "failed" &&
        job.state !== "succeeded" &&
        job.state !== "timed_out" ? (
          <div className="flex flex-wrap items-center gap-3">
            <span>Automatic updates paused</span>
            <Button
              type="button"
              variant="outline"
              onClick={() => void refreshStatus()}
            >
              Refresh status
            </Button>
          </div>
        ) : null}
      </div>

      {pollingError ? (
        <PreviewAlert title="Status unavailable">
          Automatic updates paused. Refresh status when the connection is
          available.
        </PreviewAlert>
      ) : null}

      {job.state === "timed_out" ? (
        <PreviewAlert title="Validation timed out">
          <p>
            Validation timed out before the repository could be checked safely.
          </p>
          <Button type="button" variant="outline" onClick={onRetry}>
            Retry validation
          </Button>
        </PreviewAlert>
      ) : null}

      {job.state === "failed" ? (
        <PreviewAlert title="Validation did not complete">
          <p>Validation did not complete. Review the reason, then retry.</p>
          <Button type="button" variant="outline" onClick={onRetry}>
            Retry validation
          </Button>
        </PreviewAlert>
      ) : null}

      {job.state === "succeeded" && !job.is_current ? (
        <PreviewAlert title="Preview out of date">
          This preview no longer matches the current draft. Run validation
          again.
        </PreviewAlert>
      ) : null}

      {job.state === "succeeded" &&
      job.is_current &&
      candidates.length === 0 ? (
        <PreviewAlert title="No supported layout">
          No supported localization layout was found in this source branch.
        </PreviewAlert>
      ) : null}

      {job.state === "succeeded" &&
      job.is_current &&
      candidates.length > 0 &&
      !candidatesAreExact ? (
        <PreviewAlert title="Preview cannot be confirmed">
          This preview cannot be confirmed. Review the selected repository and
          branch, then run validation again.
        </PreviewAlert>
      ) : null}

      {confirmable ? (
        <>
          <fieldset className="grid gap-3">
            <legend className="text-heading font-semibold">
              Detected layout candidates
            </legend>
            <RadioGroup
              value={selectedCandidateId}
              onValueChange={(value) => {
                setSelectedCandidateId(value);
                setConfirmedIdentity(null);
                onConfirmed(false);
              }}
              className="grid gap-3"
            >
              {candidates.map((candidate) => {
                const label = candidateLabel(candidate);
                return (
                  <label
                    key={candidate.id}
                    className="flex min-w-0 items-start gap-3 rounded-lg border p-4"
                  >
                    <RadioGroupItem value={candidate.id} aria-label={label} />
                    <span className="min-w-0 break-words [overflow-wrap:anywhere]">
                      {label}
                    </span>
                  </label>
                );
              })}
            </RadioGroup>
          </fieldset>

          {selectedCandidate === undefined ? null : (
            <CandidateDetails candidate={selectedCandidate} job={job} />
          )}

          <div className="flex flex-wrap items-center gap-3">
            <Button
              type="button"
              disabled={selectedCandidate === undefined || confirmPending}
              aria-busy={confirmPending}
              onClick={() => void submitConfirmation()}
            >
              Confirm preview
            </Button>
            {confirmed ? (
              <Badge variant="outline" className="w-fit rounded-md">
                Confirmed
              </Badge>
            ) : null}
          </div>
          {confirmError ? (
            <PreviewAlert title="Preview not confirmed">
              This preview no longer matches the current draft. Run validation
              again.
            </PreviewAlert>
          ) : null}
        </>
      ) : null}
    </div>
  );
}

function MappingPreview({
  accessToken,
  index,
  mapping,
  onConfirmed,
  productId,
}: {
  accessToken: string;
  index: number;
  mapping: AdminMappingResponse;
  onConfirmed: (mappingId: string, confirmed: boolean) => void;
  productId: string;
}) {
  const runGenerationRef = useRef(0);
  const runPendingRef = useRef(false);
  const [runPending, setRunPending] = useState(false);
  const [runError, setRunError] = useState(false);
  const [job, setJob] = useState<AdminPreviewJobResponse | null>(null);

  useEffect(
    () => () => {
      runGenerationRef.current += 1;
    },
    [],
  );

  async function runValidation() {
    if (runPendingRef.current) {
      return;
    }
    const generation = ++runGenerationRef.current;
    runPendingRef.current = true;
    setRunPending(true);
    setRunError(false);
    onConfirmed(mapping.id, false);
    try {
      const commits = await resolveCommits(accessToken, mapping);
      const response = await createAdminPreviewJob({
        auth: accessToken,
        body: {
          commits,
          expected_candidate_version: mapping.candidate_version,
        },
        path: { mapping_id: mapping.id, product_id: productId },
      });
      if (generation !== runGenerationRef.current) {
        return;
      }
      if (response.data === undefined) {
        setRunError(true);
        return;
      }
      setJob(response.data);
    } catch {
      if (generation === runGenerationRef.current) {
        setRunError(true);
      }
    } finally {
      if (generation === runGenerationRef.current) {
        runPendingRef.current = false;
        setRunPending(false);
      }
    }
  }

  return (
    <section
      id={`preview-${mapping.id}`}
      className="grid gap-6 rounded-lg border bg-secondary p-6"
      aria-labelledby={`preview-title-${mapping.id}`}
    >
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="grid gap-1">
          <h2
            id={`preview-title-${mapping.id}`}
            className="text-heading font-semibold"
          >
            Mapping {index + 1}
          </h2>
          <p className="text-muted-foreground">
            {mapping.topology === "direct" ? "Direct" : "Separate"} mapping
          </p>
        </div>
        <Button
          type="button"
          disabled={runPending}
          aria-busy={runPending}
          onClick={() => void runValidation()}
        >
          Run validation
        </Button>
      </div>

      {runError ? (
        <PreviewAlert title="Validation did not complete">
          Validation did not complete. Review the reason, then retry.
        </PreviewAlert>
      ) : null}

      {job === null ? (
        <div className="grid gap-2">
          <h3 className="text-heading font-semibold">Validation has not run</h3>
          <p className="text-muted-foreground">
            Run validation to detect files, languages, and partial translation
            samples.
          </p>
        </div>
      ) : (
        <PreviewJobView
          key={previewJobIdentity(job)}
          accessToken={accessToken}
          initialJob={job}
          onConfirmed={(confirmed) => onConfirmed(mapping.id, confirmed)}
          onRetry={() => void runValidation()}
        />
      )}
    </section>
  );
}

export function ProductPreviewPage({
  accessToken,
  productId,
}: ProductPreviewPageProps) {
  const routeProductId = useParams<"productId">().productId;
  const resolvedProductId = productId ?? routeProductId;
  const loadGenerationRef = useRef(0);
  const publicationPendingRef = useRef(false);
  const [pageState, setPageState] = useState<PageState>({ status: "loading" });
  const [confirmationState, setConfirmationState] = useState<
    Record<string, boolean>
  >({});
  const [publicationOpen, setPublicationOpen] = useState(false);
  const [publicationPending, setPublicationPending] = useState(false);
  const [blockers, setBlockers] = useState<PublicationBlocker[]>([]);
  const [publicationError, setPublicationError] = useState(false);

  const loadPage = useCallback(async () => {
    const generation = ++loadGenerationRef.current;
    setPageState({ status: "loading" });
    if (resolvedProductId === undefined) {
      setPageState({ status: "error" });
      return;
    }
    try {
      const productResult = await getAdminProduct({
        auth: accessToken,
        path: { product_id: resolvedProductId },
      });
      if (generation !== loadGenerationRef.current) {
        return;
      }
      if (productResult.data === undefined) {
        setPageState({ status: "error" });
        return;
      }
      const product = productResult.data;
      const revision =
        product.candidate_revision ??
        (!product.is_active ? product.active_revision : null);
      if (revision === null) {
        setPageState({ status: "error" });
        return;
      }
      const mappingResult = await listAdminRevisionMappings({
        auth: accessToken,
        path: {
          product_id: resolvedProductId,
          revision_id: revision.id,
        },
        query: { cursor: null, limit: 50 },
      });
      if (generation !== loadGenerationRef.current) {
        return;
      }
      if (mappingResult.data === undefined) {
        setPageState({ status: "error" });
        return;
      }
      setConfirmationState({});
      setPageState({
        status: "ready",
        mappings: mappingResult.data.items,
        product,
        productId: resolvedProductId,
      });
    } catch {
      if (generation === loadGenerationRef.current) {
        setPageState({ status: "error" });
      }
    }
  }, [accessToken, resolvedProductId]);

  useEffect(() => {
    let active = true;
    queueMicrotask(() => {
      if (active) {
        void loadPage();
      }
    });
    return () => {
      active = false;
      loadGenerationRef.current += 1;
    };
  }, [loadPage]);

  const updateConfirmation = useCallback(
    (mappingId: string, confirmed: boolean) => {
      setConfirmationState((current) =>
        current[mappingId] === confirmed
          ? current
          : { ...current, [mappingId]: confirmed },
      );
    },
    [],
  );

  if (pageState.status === "loading") {
    return (
      <section className="grid gap-6">
        <h1 className="text-display font-semibold">Preview</h1>
        <div className="grid gap-4" role="status" aria-live="polite">
          <Skeleton className="h-8 w-48 max-w-full" />
          <Skeleton className="h-56 w-full" />
          <span>Loading product preview</span>
        </div>
      </section>
    );
  }

  if (pageState.status === "error") {
    return (
      <section className="grid gap-6">
        <h1 className="text-display font-semibold">Preview</h1>
        <PreviewAlert title="Product preview unavailable">
          <p>
            We could not load this page. Retry without leaving the
            administration area.
          </p>
          <Button
            type="button"
            variant="outline"
            onClick={() => void loadPage()}
          >
            Retry loading page
          </Button>
        </PreviewAlert>
      </section>
    );
  }

  const { mappings, product: currentProduct } = pageState;
  const readyState = pageState;
  const isReactivation =
    !currentProduct.is_active &&
    currentProduct.active_revision !== null &&
    currentProduct.candidate_revision === null;
  const allConfirmed =
    mappings.length > 0 &&
    mappings.every((mapping) =>
      isReactivation
        ? hasPublishedPreviewConfirmation(mapping)
        : confirmationState[mapping.id] === true,
    );
  const publishLabel =
    currentProduct.active_revision === null
      ? "Publish product"
      : "Publish changes";
  const actionLabel = isReactivation ? "Reactivate product" : publishLabel;
  const showAction =
    isReactivation || currentProduct.candidate_revision !== null;

  async function submitPublication() {
    if (publicationPendingRef.current || !allConfirmed) {
      return;
    }
    publicationPendingRef.current = true;
    setPublicationPending(true);
    setPublicationError(false);
    setBlockers([]);
    try {
      const result = isReactivation
        ? await reactivateAdminProduct({
            auth: accessToken,
            body: {
              active_revision_id: currentProduct.active_revision!.id,
              expected_active_version: currentProduct.active_revision!.version,
            },
            path: { product_id: readyState.productId },
          })
        : await publishAdminProductCandidate({
            auth: accessToken,
            body: {
              candidate_revision_id: currentProduct.candidate_revision!.id,
              expected_candidate_version:
                currentProduct.candidate_revision!.version,
            },
            path: { product_id: readyState.productId },
          });
      if (result.data === undefined) {
        if (responseStatus(result) === 409) {
          setBlockers(publicationBlockers(result.error));
        } else {
          setPublicationError(true);
        }
        setPublicationOpen(false);
        return;
      }
      setPageState({ ...readyState, product: result.data });
      setPublicationOpen(false);
      toast.success(
        isReactivation ? "Product reactivated" : "Product published",
      );
    } catch {
      setPublicationError(true);
    } finally {
      publicationPendingRef.current = false;
      setPublicationPending(false);
    }
  }

  return (
    <section className="grid min-w-0 max-w-full gap-8 overflow-x-clip">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="grid min-w-0 gap-2">
          <h1 className="text-display font-semibold">Preview</h1>
          <p className="break-words text-muted-foreground">
            {isReactivation
              ? `Review the confirmed published configuration for ${currentProduct.name}.`
              : `Validate and explicitly confirm the current draft for ${currentProduct.name}.`}
          </p>
        </div>
        <Badge variant="outline" className="w-fit rounded-md">
          {currentProduct.is_active ? "Active" : "Inactive"}
        </Badge>
      </div>

      {mappings.length === 0 ? (
        <Alert>
          <AlertTitle>No mappings configured</AlertTitle>
          <AlertDescription>
            Add a mapping that represents one localization format and layout.
          </AlertDescription>
        </Alert>
      ) : (
        mappings.map((mapping, index) =>
          isReactivation ? (
            <section
              id={`preview-${mapping.id}`}
              key={mapping.id}
              className="grid gap-3 rounded-lg border bg-secondary p-6"
              aria-labelledby={`preview-title-${mapping.id}`}
            >
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="grid gap-1">
                  <h2
                    id={`preview-title-${mapping.id}`}
                    className="text-heading font-semibold"
                  >
                    Mapping {index + 1}
                  </h2>
                  <p className="text-muted-foreground">
                    {mapping.topology === "direct" ? "Direct" : "Separate"}{" "}
                    published mapping
                  </p>
                </div>
                <Badge variant="outline" className="w-fit rounded-md">
                  {hasPublishedPreviewConfirmation(mapping)
                    ? "Confirmed"
                    : "Preview confirmation required"}
                </Badge>
              </div>
            </section>
          ) : (
            <MappingPreview
              key={mapping.id}
              accessToken={accessToken}
              index={index}
              mapping={mapping}
              onConfirmed={updateConfirmation}
              productId={readyState.productId}
            />
          ),
        )
      )}

      {publicationError ? (
        <PreviewAlert title="Publication did not complete">
          The current product configuration remains unchanged. Try again.
        </PreviewAlert>
      ) : null}

      {blockers.length > 0 ? (
        <Alert variant="destructive" aria-label="Publication blocked">
          <AlertTitle>Publication blocked</AlertTitle>
          <AlertDescription>
            <ul className="grid gap-2">
              {blockers.map((blocker) => (
                <li key={blocker}>{BLOCKER_LABELS[blocker]}</li>
              ))}
            </ul>
            <ul className="grid gap-2">
              {mappings.map((mapping, index) => (
                <li key={mapping.id}>
                  <a
                    className="text-accent underline"
                    href={`#preview-${mapping.id}`}
                  >
                    Review mapping {index + 1}
                  </a>
                </li>
              ))}
            </ul>
          </AlertDescription>
        </Alert>
      ) : null}

      {showAction ? (
        <section className="grid gap-4 rounded-lg border bg-secondary p-6">
          <h2 className="text-heading font-semibold">Review and publish</h2>
          {!allConfirmed ? (
            <ul className="grid gap-2">
              {mappings.map((mapping, index) =>
                (isReactivation && hasPublishedPreviewConfirmation(mapping)) ||
                (!isReactivation &&
                  confirmationState[mapping.id] === true) ? null : (
                  <li key={mapping.id}>
                    <a
                      className="text-accent underline"
                      href={`#preview-${mapping.id}`}
                    >
                      Mapping {index + 1}: Preview confirmation required
                    </a>
                  </li>
                ),
              )}
            </ul>
          ) : null}
          <Button
            type="button"
            className="w-full sm:w-fit"
            disabled={!allConfirmed}
            onClick={() => setPublicationOpen(true)}
          >
            {actionLabel}
          </Button>
        </section>
      ) : null}

      {publicationOpen ? (
        <AlertDialog
          open
          onOpenChange={(open) => {
            if (!publicationPendingRef.current) {
              setPublicationOpen(open);
            }
          }}
        >
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>
                {isReactivation
                  ? `Reactivate ${currentProduct.name}?`
                  : `Publish ${currentProduct.name}?`}
              </AlertDialogTitle>
              <AlertDialogDescription>
                {isReactivation
                  ? "Its confirmed published mappings will resume operating."
                  : `The validated draft will atomically replace the current configuration for ${mappings.length} ${mappings.length === 1 ? "mapping" : "mappings"}.`}
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel disabled={publicationPending}>
                Cancel
              </AlertDialogCancel>
              <Button
                type="button"
                disabled={publicationPending}
                aria-busy={publicationPending}
                onClick={() => void submitPublication()}
              >
                {actionLabel}
              </Button>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      ) : null}
    </section>
  );
}
