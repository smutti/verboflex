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
  confirmAdminActiveRevisionRevalidation,
  confirmAdminPreviewJob,
  createAdminActiveRevisionRevalidationJob,
  createAdminPreviewJob,
  getAdminRepositoryBranch,
  getAdminActiveRevisionRevalidationJob,
  getAdminProduct,
  getAdminProductReactivationEligibility,
  listAdminRevisionMappings,
  publishAdminProductCandidate,
  reactivateAdminProduct,
  type AdminActiveRevisionRevalidationJobResponse,
  type AdminMappingResponse,
  type AdminPreviewCommitRequest,
  type AdminPreviewJobResponse,
  type AdminPreviewLayoutCandidateResponse,
  type AdminProductReactivationEligibilityResponse,
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
import { useCursorCollection } from "../useCursorCollection";
import {
  nextPreviewPollDelay,
  previewJobIdentity,
  usePreviewPolling,
} from "./usePreviewPolling";

export interface ProductPreviewPageProps {
  accessToken: string;
  productId?: string;
}

type PageState =
  | { status: "loading" }
  | { status: "error" }
  | {
      status: "ready";
      product: AdminProductResponse;
      productId: string;
      revisionId: string;
      revisionVersion: number;
    };

type ReactivationEligibilityState =
  | { status: "idle" | "loading" | "error" }
  | {
      data: AdminProductReactivationEligibilityResponse;
      status: "ready";
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

function activeRevalidationJobIdentity(
  job: AdminActiveRevisionRevalidationJobResponse,
) {
  return JSON.stringify({
    activeRevisionId: job.active_revision_id,
    activeRevisionVersion: job.active_revision_version,
    attempt: job.attempt,
    connectionGeneration: job.connection_generation,
    detectorVersion: job.detector_version,
    id: job.id,
    inputDigest: job.input_digest,
    mappingId: job.mapping_id,
    productId: job.product_id,
    repositorySides: job.repository_sides.map((side) => ({
      commitHash: side.commit_hash,
      repositoryId: side.repository_id,
      role: side.role,
      sourceBranch: side.source_branch,
    })),
  });
}

function activeRevalidationPollingExhausted(
  job: AdminActiveRevisionRevalidationJobResponse,
) {
  if (
    job.state === "failed" ||
    job.state === "succeeded" ||
    job.state === "timed_out"
  ) {
    return false;
  }
  const createdAt = Date.parse(job.created_at);
  const elapsed = Number.isFinite(createdAt) ? Date.now() - createdAt : 0;
  return nextPreviewPollDelay(elapsed) === null;
}

type ConfiguredPreviewSourceSide = {
  branch: string;
  repositoryId: string;
  role: AdminPreviewCommitRequest["role"];
};

function configuredPreviewSourceSides(
  mapping: AdminMappingResponse,
): ConfiguredPreviewSourceSide[] {
  return mapping.topology === "direct"
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
}

async function resolveConfiguredBranchCommit(
  accessToken: string,
  side: ConfiguredPreviewSourceSide,
): Promise<AdminPreviewCommitRequest> {
  if (side.branch === "" || side.repositoryId === "") {
    throw new Error();
  }
  const result = await getAdminRepositoryBranch({
    auth: accessToken,
    path: { repository_id: side.repositoryId },
    query: { branch_name: side.branch },
  });
  if (result.data === undefined || result.data.name !== side.branch) {
    throw new Error();
  }
  return { commit_hash: result.data.commit_hash, role: side.role };
}

async function resolveCommits(
  accessToken: string,
  mapping: AdminMappingResponse,
) {
  return Promise.all(
    configuredPreviewSourceSides(mapping).map((side) =>
      resolveConfiguredBranchCommit(accessToken, side),
    ),
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
  job: {
    repository_sides: AdminPreviewJobResponse["repository_sides"];
  };
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
          base_language: null,
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
  collectionReady,
  index,
  mapping,
  onConfirmed,
  productId,
}: {
  accessToken: string;
  collectionReady: boolean;
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
    if (runPendingRef.current || !collectionReady) {
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
          disabled={runPending || !collectionReady}
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

function PublishedMappingRecovery({
  accessToken,
  eligibilityReady,
  index,
  isCurrent,
  mapping,
  onConfirmed,
  productId,
  revisionId,
  revisionVersion,
}: {
  accessToken: string;
  eligibilityReady: boolean;
  index: number;
  isCurrent: boolean;
  mapping: AdminMappingResponse;
  onConfirmed: () => Promise<void>;
  productId: string;
  revisionId: string;
  revisionVersion: number;
}) {
  const runButtonRef = useRef<HTMLButtonElement>(null);
  const runGenerationRef = useRef(0);
  const runPendingRef = useRef(false);
  const [announcement, setAnnouncement] = useState("");
  const [confirmError, setConfirmError] = useState(false);
  const [confirmPending, setConfirmPending] = useState(false);
  const confirmPendingRef = useRef(false);
  const [confirmedIdentity, setConfirmedIdentity] = useState<string | null>(
    null,
  );
  const [job, setJob] =
    useState<AdminActiveRevisionRevalidationJobResponse | null>(null);
  const [pollingError, setPollingError] = useState(false);
  const [runError, setRunError] = useState(false);
  const [runPending, setRunPending] = useState(false);
  const [selectedCandidateId, setSelectedCandidateId] = useState("");

  useEffect(
    () => () => {
      runGenerationRef.current += 1;
    },
    [],
  );

  const result = job?.result ?? null;
  const candidates = result?.layout_candidates ?? [];
  const candidatesAreExact =
    candidates.length > 0 && candidates.every(isExactCandidate);
  const confirmable =
    job?.state === "succeeded" &&
    job.is_current &&
    result !== null &&
    candidatesAreExact;
  const selectedCandidate = candidates.find(
    (candidate) => candidate.id === selectedCandidateId,
  );
  const currentConfirmationIdentity =
    job === null || result === null || selectedCandidate === undefined
      ? null
      : `${activeRevalidationJobIdentity(job)}:${result.digest}:${selectedCandidate.id}`;
  const confirmed =
    currentConfirmationIdentity !== null &&
    confirmedIdentity === currentConfirmationIdentity;

  const focusRecoveryControl = useCallback(() => {
    queueMicrotask(() => runButtonRef.current?.focus());
  }, []);

  useEffect(() => {
    if (
      job === null ||
      job.state === "failed" ||
      job.state === "succeeded" ||
      job.state === "timed_out"
    ) {
      return;
    }
    const generation = runGenerationRef.current;
    const identity = activeRevalidationJobIdentity(job);
    const createdAt = Date.parse(job.created_at);
    const elapsed = Number.isFinite(createdAt) ? Date.now() - createdAt : 0;
    const delay = nextPreviewPollDelay(elapsed);
    if (delay === null) {
      return;
    }
    const timer = window.setTimeout(() => {
      void (async () => {
        try {
          const response = await getAdminActiveRevisionRevalidationJob({
            auth: accessToken,
            path: { job_id: job.id },
          });
          if (generation !== runGenerationRef.current) {
            return;
          }
          if (
            response.data === undefined ||
            activeRevalidationJobIdentity(response.data) !== identity
          ) {
            setAnnouncement("Validation status is unavailable. Try again.");
            setPollingError(true);
            focusRecoveryControl();
            return;
          }
          const pollingExhausted = activeRevalidationPollingExhausted(
            response.data,
          );
          setPollingError(pollingExhausted);
          setAnnouncement(
            pollingExhausted
              ? "Automatic updates paused. Try again."
              : JOB_LABELS[response.data.state],
          );
          setJob(response.data);
          if (
            pollingExhausted ||
            response.data.state === "failed" ||
            response.data.state === "timed_out"
          ) {
            focusRecoveryControl();
          }
        } catch {
          if (generation === runGenerationRef.current) {
            setAnnouncement("Validation status is unavailable. Try again.");
            setPollingError(true);
            focusRecoveryControl();
          }
        }
      })();
    }, delay);
    return () => window.clearTimeout(timer);
  }, [accessToken, focusRecoveryControl, job]);

  async function runValidationAgain() {
    if (runPendingRef.current) {
      return;
    }
    const generation = ++runGenerationRef.current;
    runPendingRef.current = true;
    setRunPending(true);
    setRunError(false);
    setPollingError(false);
    setConfirmError(false);
    setConfirmedIdentity(null);
    setSelectedCandidateId("");
    try {
      const commits = await resolveCommits(accessToken, mapping);
      const response = await createAdminActiveRevisionRevalidationJob({
        auth: accessToken,
        body: {
          commits,
          expected_active_revision_version: revisionVersion,
        },
        path: {
          mapping_id: mapping.id,
          product_id: productId,
          revision_id: revisionId,
        },
      });
      if (generation !== runGenerationRef.current) {
        return;
      }
      if (response.data === undefined) {
        setAnnouncement("Validation did not complete. Try again.");
        setRunError(true);
        focusRecoveryControl();
        return;
      }
      const pollingExhausted = activeRevalidationPollingExhausted(
        response.data,
      );
      setPollingError(pollingExhausted);
      setAnnouncement(
        pollingExhausted
          ? "Automatic updates paused. Try again."
          : JOB_LABELS[response.data.state],
      );
      setJob(response.data);
      if (pollingExhausted) {
        focusRecoveryControl();
      }
    } catch {
      if (generation === runGenerationRef.current) {
        setAnnouncement("Validation did not complete. Try again.");
        setRunError(true);
        focusRecoveryControl();
      }
    } finally {
      if (generation === runGenerationRef.current) {
        runPendingRef.current = false;
        setRunPending(false);
      }
    }
  }

  async function submitConfirmation() {
    if (
      confirmPendingRef.current ||
      !confirmable ||
      job === null ||
      result === null ||
      selectedCandidate === undefined ||
      currentConfirmationIdentity === null
    ) {
      return;
    }
    confirmPendingRef.current = true;
    setConfirmPending(true);
    setConfirmError(false);
    try {
      const response = await confirmAdminActiveRevisionRevalidation({
        auth: accessToken,
        body: {
          active_revision_id: job.active_revision_id,
          active_revision_version: job.active_revision_version,
          base_language: null,
          commits: job.repository_sides.map((side) => ({
            commit_hash: side.commit_hash,
            role: side.role,
          })),
          connection_generation: job.connection_generation,
          layout_candidate_id: selectedCandidate.id,
          layout_candidate_version: selectedCandidate.version,
          mapping_id: job.mapping_id,
          preview_digest: result.digest,
        },
        path: { job_id: job.id },
      });
      if (response.data === undefined) {
        setAnnouncement("Preview was not confirmed. Run validation again.");
        setConfirmError(true);
        focusRecoveryControl();
        return;
      }
      setConfirmedIdentity(currentConfirmationIdentity);
      setAnnouncement("Confirmed");
      await onConfirmed();
    } catch {
      setAnnouncement("Preview was not confirmed. Run validation again.");
      setConfirmError(true);
      focusRecoveryControl();
    } finally {
      confirmPendingRef.current = false;
      setConfirmPending(false);
    }
  }

  return (
    <section
      id={`preview-${mapping.id}`}
      className="grid gap-6 rounded-lg border bg-secondary p-6"
      aria-labelledby={`preview-title-${mapping.id}`}
    >
      <div
        role="status"
        aria-label="Active revision recovery status"
        aria-live="polite"
        aria-atomic="true"
        className="sr-only"
      >
        {announcement}
      </div>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="grid gap-1">
          <h2
            id={`preview-title-${mapping.id}`}
            className="text-heading font-semibold"
          >
            Mapping {index + 1}
          </h2>
          <p className="text-muted-foreground">
            {mapping.topology === "direct" ? "Direct" : "Separate"} published
            mapping
          </p>
        </div>
        {eligibilityReady && isCurrent ? (
          <Badge variant="outline" className="w-fit rounded-md">
            Confirmed
          </Badge>
        ) : !eligibilityReady ? (
          <Badge variant="outline" className="w-fit rounded-md">
            Checking confirmation
          </Badge>
        ) : (
          <Button
            ref={runButtonRef}
            type="button"
            disabled={runPending}
            aria-busy={runPending}
            onClick={() => void runValidationAgain()}
          >
            Run validation again
          </Button>
        )}
      </div>

      {eligibilityReady && !isCurrent ? (
        <PreviewAlert title="Preview out of date">
          This preview no longer matches the current draft. Run validation
          again.
        </PreviewAlert>
      ) : null}

      {runError ? (
        <PreviewAlert title="Validation did not complete">
          Validation did not complete. Try again.
        </PreviewAlert>
      ) : null}

      {pollingError ? (
        <PreviewAlert title="Status unavailable">
          Validation status is unavailable. Try again.
        </PreviewAlert>
      ) : null}

      {job === null || isCurrent ? null : (
        <div className="grid gap-6">
          <Badge variant="outline" className="w-fit rounded-md">
            {JOB_LABELS[job.state]}
          </Badge>

          {job.state === "failed" || job.state === "timed_out" ? (
            <PreviewAlert title="Validation did not complete">
              Validation did not complete. Run validation again.
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
                        <RadioGroupItem
                          value={candidate.id}
                          aria-label={label}
                        />
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
            </>
          ) : null}

          {confirmError ? (
            <PreviewAlert title="Preview not confirmed">
              Preview was not confirmed. Run validation again.
            </PreviewAlert>
          ) : null}
        </div>
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
  const eligibilityGenerationRef = useRef(0);
  const loadGenerationRef = useRef(0);
  const publicationPendingRef = useRef(false);
  const [pageState, setPageState] = useState<PageState>({ status: "loading" });
  const [reactivationEligibilityState, setReactivationEligibilityState] =
    useState<ReactivationEligibilityState>({ status: "idle" });
  const [confirmationState, setConfirmationState] = useState<
    Record<string, boolean>
  >({});
  const [publicationOpen, setPublicationOpen] = useState(false);
  const [publicationPending, setPublicationPending] = useState(false);
  const [blockers, setBlockers] = useState<PublicationBlocker[]>([]);
  const [publicationError, setPublicationError] = useState(false);

  const loadPage = useCallback(async () => {
    const generation = ++loadGenerationRef.current;
    eligibilityGenerationRef.current += 1;
    setReactivationEligibilityState({ status: "idle" });
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
      setConfirmationState({});
      setPageState({
        status: "ready",
        product,
        productId: resolvedProductId,
        revisionId: revision.id,
        revisionVersion: revision.version,
      });
    } catch {
      if (generation === loadGenerationRef.current) {
        setPageState({ status: "error" });
      }
    }
  }, [accessToken, resolvedProductId]);

  const loadMappingPage = useCallback(
    async (cursor: string | null) => {
      if (pageState.status !== "ready") {
        return { items: [], next_cursor: null };
      }
      const result = await listAdminRevisionMappings({
        auth: accessToken,
        path: {
          product_id: pageState.productId,
          revision_id: pageState.revisionId,
        },
        query: { cursor, limit: 50 },
      });
      if (result.data === undefined) {
        throw new Error("mapping page unavailable");
      }
      return result.data;
    },
    [accessToken, pageState],
  );
  const mappingQueryKey =
    pageState.status === "ready"
      ? JSON.stringify([
          "preview-revision-mappings",
          accessToken,
          pageState.productId,
          pageState.revisionId,
          pageState.revisionVersion,
        ])
      : `preview-revision-mappings:${pageState.status}`;
  const mappingCollection = useCursorCollection({
    getItemId: (mapping: AdminMappingResponse) => mapping.id,
    loadPage: loadMappingPage,
    queryKey: mappingQueryKey,
  });
  const {
    isEnd: mappingCollectionComplete,
    items: collectedMappings,
    loadMore: loadMoreMappings,
    loadMoreError: mappingLoadMoreError,
    loadingMore: mappingLoadingMore,
    nextCursor: mappingNextCursor,
    reload: reloadMappings,
    status: mappingCollectionStatus,
  } = mappingCollection;

  useEffect(() => {
    if (
      mappingCollectionStatus === "ready" &&
      mappingNextCursor !== null &&
      !mappingLoadingMore &&
      !mappingLoadMoreError
    ) {
      void loadMoreMappings();
    }
  }, [
    loadMoreMappings,
    mappingCollectionStatus,
    mappingLoadMoreError,
    mappingLoadingMore,
    mappingNextCursor,
  ]);

  useEffect(() => {
    let active = true;
    queueMicrotask(() => {
      if (active) {
        void loadPage();
      }
    });
    return () => {
      active = false;
      eligibilityGenerationRef.current += 1;
      loadGenerationRef.current += 1;
    };
  }, [loadPage]);

  const loadReactivationEligibility = useCallback(async () => {
    if (
      pageState.status !== "ready" ||
      pageState.product.is_active ||
      pageState.product.active_revision === null ||
      pageState.product.candidate_revision !== null ||
      !mappingCollectionComplete
    ) {
      setReactivationEligibilityState({ status: "idle" });
      return;
    }
    const generation = ++eligibilityGenerationRef.current;
    const activeRevision = pageState.product.active_revision;
    setReactivationEligibilityState({ status: "loading" });
    try {
      const response = await getAdminProductReactivationEligibility({
        auth: accessToken,
        path: {
          product_id: pageState.productId,
          revision_id: activeRevision.id,
        },
        query: {
          expected_active_revision_version: activeRevision.version,
        },
      });
      if (generation !== eligibilityGenerationRef.current) {
        return;
      }
      if (
        response.data === undefined ||
        response.data.product_id !== pageState.productId ||
        response.data.active_revision_id !== activeRevision.id ||
        response.data.active_revision_version !== activeRevision.version
      ) {
        setReactivationEligibilityState({ status: "error" });
        return;
      }
      setReactivationEligibilityState({
        data: response.data,
        status: "ready",
      });
    } catch {
      if (generation === eligibilityGenerationRef.current) {
        setReactivationEligibilityState({ status: "error" });
      }
    }
  }, [accessToken, mappingCollectionComplete, pageState]);

  useEffect(() => {
    let active = true;
    queueMicrotask(() => {
      if (active) {
        void loadReactivationEligibility();
      }
    });
    return () => {
      active = false;
    };
  }, [loadReactivationEligibility]);

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

  if (mappingCollectionStatus === "loading") {
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

  if (mappingCollectionStatus === "error") {
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
            onClick={() => void reloadMappings()}
          >
            Retry loading page
          </Button>
        </PreviewAlert>
      </section>
    );
  }

  const mappings = collectedMappings;
  const { product: currentProduct } = pageState;
  const readyState = pageState;
  const collectionReady = mappingCollectionComplete;
  const isReactivation =
    !currentProduct.is_active &&
    currentProduct.active_revision !== null &&
    currentProduct.candidate_revision === null;
  const reactivationEligibility =
    reactivationEligibilityState.status === "ready"
      ? reactivationEligibilityState.data
      : null;
  const reactivationMappingCurrentness = new Map(
    reactivationEligibility?.mappings.map((mapping) => [
      mapping.mapping_id,
      mapping.is_current,
    ]) ?? [],
  );
  const allConfirmed =
    collectionReady &&
    mappings.length > 0 &&
    (isReactivation
      ? reactivationEligibility !== null &&
        reactivationEligibility.eligible &&
        reactivationEligibility.mappings.length === mappings.length &&
        mappings.every(
          (mapping) => reactivationMappingCurrentness.get(mapping.id) === true,
        )
      : mappings.every((mapping) => confirmationState[mapping.id] === true));
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
    const submissionGeneration = loadGenerationRef.current;
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
      if (submissionGeneration !== loadGenerationRef.current) {
        return;
      }
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
      if (submissionGeneration === loadGenerationRef.current) {
        setPublicationError(true);
      }
    } finally {
      publicationPendingRef.current = false;
      if (submissionGeneration === loadGenerationRef.current) {
        setPublicationPending(false);
      }
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

      {!collectionReady && !mappingLoadMoreError ? (
        <Alert aria-label="Loading complete mapping set">
          <AlertTitle>Loading all mappings</AlertTitle>
          <AlertDescription>
            Loading complete mapping set: {mappings.length}{" "}
            {mappings.length === 1 ? "mapping" : "mappings"} loaded.
          </AlertDescription>
        </Alert>
      ) : null}

      {mappingLoadMoreError ? (
        <Alert variant="destructive" aria-label="Mapping collection incomplete">
          <AlertTitle>Mapping collection incomplete</AlertTitle>
          <AlertDescription>
            <p>
              {mappings.length} {mappings.length === 1 ? "mapping" : "mappings"}{" "}
              loaded. The complete revision mapping set is required before
              validation or lifecycle actions are available.
            </p>
            <Button
              type="button"
              variant="outline"
              disabled={mappingLoadingMore}
              aria-busy={mappingLoadingMore}
              onClick={() => void loadMoreMappings()}
            >
              Retry loading mappings
            </Button>
          </AlertDescription>
        </Alert>
      ) : null}

      {isReactivation && reactivationEligibilityState.status === "error" ? (
        <PreviewAlert title="Reactivation status unavailable">
          <p>The current confirmation state could not be checked. Try again.</p>
          <Button
            type="button"
            variant="outline"
            onClick={() => void loadReactivationEligibility()}
          >
            Retry confirmation check
          </Button>
        </PreviewAlert>
      ) : null}

      {collectionReady && mappings.length === 0 ? (
        <Alert>
          <AlertTitle>No mappings configured</AlertTitle>
          <AlertDescription>
            Add a mapping that represents one localization format and layout.
          </AlertDescription>
        </Alert>
      ) : (
        mappings.map((mapping, index) =>
          isReactivation ? (
            <PublishedMappingRecovery
              key={mapping.id}
              accessToken={accessToken}
              eligibilityReady={reactivationEligibility !== null}
              index={index}
              isCurrent={
                reactivationMappingCurrentness.get(mapping.id) === true
              }
              mapping={mapping}
              onConfirmed={loadReactivationEligibility}
              productId={readyState.productId}
              revisionId={readyState.revisionId}
              revisionVersion={readyState.revisionVersion}
            />
          ) : (
            <MappingPreview
              key={mapping.id}
              accessToken={accessToken}
              collectionReady={collectionReady}
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
                (isReactivation &&
                  reactivationMappingCurrentness.get(mapping.id) === true) ||
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
