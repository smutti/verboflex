import { t, useUiLanguage } from "@/i18n";
import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { Link, useParams } from "react-router-dom";
import { toast } from "sonner";

import {
  confirmAdminActiveRevisionRevalidation,
  confirmAdminPreviewJob,
  createAdminActiveRevisionRevalidationJob,
  createAdminPreviewJob,
  getAdminRepositoryBranch,
  getAdminRepository,
  getAdminActiveRevisionRevalidationJob,
  getAdminLatestActiveRevisionRevalidationJob,
  getAdminLatestCandidatePreviewJob,
  getAdminProduct,
  getAdminProductReactivationEligibility,
  listAdminRevisionMappings,
  publishAdminProductCandidate,
  reactivateAdminProduct,
  type AdminActiveRevisionRevalidationJobResponse,
  type AdminActiveRevisionRevalidationConfirmationResponse,
  type AdminMappingResponse,
  type AdminPreviewCommitRequest,
  type AdminPreviewConfirmationResponse,
  type AdminPreviewJobResponse,
  type AdminPreviewLayoutCandidateResponse,
  type AdminProductReactivationEligibilityResponse,
  type AdminProductResponse,
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
import { Input } from "../../../components/ui/input";
import { Label } from "../../../components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "../../../components/ui/select";
import { Skeleton } from "../../../components/ui/skeleton";
import { useCursorCollection } from "../useCursorCollection";
import { PublishedMappingImports } from "../imports/PublishedMappingImports";
import { DuplicateKeysDialog } from "../imports/DuplicateKeysDialog";
import {
  nextPreviewPollDelay,
  previewJobIdentity,
  usePreviewPolling,
} from "./usePreviewPolling";

export interface ProductPreviewPageProps {
  accessToken: string;
  productId?: string;
  embedded?: boolean;
  onProductPublished?: (product: AdminProductResponse) => void;
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
  get failed() {
    return t("Failed");
  },
  get queued() {
    return t("Queued");
  },
  get running() {
    return t("Running");
  },
  get succeeded() {
    return t("Succeeded");
  },
  get timed_out() {
    return t("Timed out");
  },
};

function hasActionableDuplicateReport(
  job: AdminPreviewJobResponse | AdminActiveRevisionRevalidationJobResponse,
) {
  const summary = job.duplicate_report_summary;
  return summary !== undefined && summary !== null
    ? summary.group_count > 0 || !summary.complete
    : false;
}

const FORMAT_LABELS: Record<
  AdminPreviewLayoutCandidateResponse["format"],
  string
> = {
  android_xml: "Android XML",
  ios_strings: "iOS strings",
  json: "JSON",
  get qt_ts() {
    return t("Qt TS");
  },
  xliff: "XLIFF",
};

const BLOCKER_LABELS: Record<PublicationBlocker, string> = {
  get layout_required() {
    return t("Layout selection required");
  },
  get mapping_configuration_invalid() {
    return t("Mapping configuration invalid");
  },
  get mappings_required() {
    return t("At least one mapping is required");
  },
  get preview_confirmation_required() {
    return t("Preview confirmation required");
  },
  get target_configuration_invalid() {
    return t("Target configuration invalid");
  },
};

function detectedLanguages(
  candidates: readonly AdminPreviewLayoutCandidateResponse[],
) {
  return [
    ...new Set(
      candidates
        .filter((candidate) => candidate.repository_side !== "keys")
        .flatMap((candidate) => candidate.languages)
        .filter((language) => language !== "default"),
    ),
  ].sort();
}

function confirmationCandidate(
  candidates: readonly AdminPreviewLayoutCandidateResponse[],
  baseLanguage: string,
  preferredId?: string | null,
) {
  const matches = candidates.filter(
    (candidate) =>
      candidate.repository_side !== "keys" &&
      isCanonicalBaseLanguage(baseLanguage) &&
      (candidate.languages.includes(baseLanguage) ||
        candidate.languages.includes("default")),
  );
  return (
    matches.find((candidate) => candidate.id === preferredId) ?? matches[0]
  );
}

function hasDefaultLanguage(
  candidates: readonly AdminPreviewLayoutCandidateResponse[],
) {
  return candidates.some(
    (candidate) =>
      candidate.repository_side !== "keys" &&
      candidate.languages.includes("default"),
  );
}

function isCanonicalBaseLanguage(value: string) {
  // The same bounded canonical locale grammar used by preview confirmation.
  return /^[a-z]{2,3}(?:-[A-Z][a-z]{3})?(?:-(?:[A-Z]{2}|[0-9]{3}))?$/.test(
    value,
  );
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

function isExactCandidateWithoutLanguage(
  candidate: AdminPreviewLayoutCandidateResponse,
) {
  return (
    candidate.confidence === 1 &&
    candidate.files.length > 0 &&
    candidate.keys.length > 0 &&
    candidate.samples.length > 0
  );
}

function isBaseLanguageRequired(error: unknown) {
  return (
    typeof error === "object" &&
    error !== null &&
    "detail" in error &&
    error.detail === "base_language_required"
  );
}

function previewConfirmationMatches(
  confirmation: AdminPreviewConfirmationResponse,
  job: AdminPreviewJobResponse,
  candidate: AdminPreviewLayoutCandidateResponse,
  baseLanguage: string,
) {
  return (
    confirmation.job_id === job.id &&
    confirmation.mapping_id === job.mapping_id &&
    // The server binds base_language into this digest after validating the
    // original request digest. Do not compare it with the unbound preview digest.
    /^[0-9a-f]{64}$/.test(confirmation.preview_digest) &&
    confirmation.layout_candidate_id === candidate.id &&
    confirmation.layout_candidate_version === candidate.version &&
    confirmation.base_language === baseLanguage
  );
}

function activeConfirmationMatches(
  confirmation: AdminActiveRevisionRevalidationConfirmationResponse,
  job: AdminActiveRevisionRevalidationJobResponse,
  candidate: AdminPreviewLayoutCandidateResponse,
  baseLanguage: string,
) {
  return (
    confirmation.job_id === job.id &&
    confirmation.product_id === job.product_id &&
    confirmation.active_revision_id === job.active_revision_id &&
    confirmation.active_revision_version === job.active_revision_version &&
    confirmation.mapping_id === job.mapping_id &&
    confirmation.connection_generation === job.connection_generation &&
    /^[0-9a-f]{64}$/.test(confirmation.preview_digest) &&
    confirmation.layout_candidate_id === candidate.id &&
    confirmation.layout_candidate_version === candidate.version &&
    confirmation.base_language === baseLanguage
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
  tone = "error",
}: {
  children: ReactNode;
  title: string;
  tone?: "error" | "warning";
}) {
  useUiLanguage();
  return (
    <Alert
      variant={tone === "error" ? "destructive" : "default"}
      className={
        tone === "warning"
          ? "border-amber-500/50 bg-amber-50 text-amber-950 dark:bg-amber-950/30 dark:text-amber-100"
          : undefined
      }
    >
      <AlertTitle>{title}</AlertTitle>
      <AlertDescription>{children}</AlertDescription>
    </Alert>
  );
}

type DuplicateReportSummary = NonNullable<
  AdminPreviewJobResponse["duplicate_report_summary"]
>;

function DuplicateValidationAlert({
  summary,
}: {
  summary: DuplicateReportSummary;
}) {
  useUiLanguage();
  const groupLabel = summary.group_count === 1 ? "group" : "groups";
  const occurrenceLabel =
    summary.repeated_occurrences === 1 ? "occurrence" : "occurrences";
  return summary.group_count > 0 ? (
    <PreviewAlert title={t("Duplicate keys detected")} tone="warning">
      {summary.group_count} {t(" duplicate ")}
      {groupLabel} {t(" and")} {summary.repeated_occurrences} {t(" repeated ")}
      {occurrenceLabel}{" "}
      {t(
        " were found in this mapping. Unique strings remain available while duplicate identities are quarantined. Open “View duplicate keys” to inspect them and correct the source repository.",
      )}
    </PreviewAlert>
  ) : (
    <PreviewAlert title={t("Duplicate-key scan incomplete")}>
      {t(
        "Duplicate-key validation could not inspect the complete mapping. Review the diagnostic details, correct the source repository, then run validation again.",
      )}
    </PreviewAlert>
  );
}

function SourceDetails({
  candidates,
  job,
}: {
  candidates: readonly AdminPreviewLayoutCandidateResponse[];
  job: { repository_sides: AdminPreviewJobResponse["repository_sides"] };
}) {
  useUiLanguage();
  const languages = detectedLanguages(candidates);
  const files = candidates.flatMap((candidate) =>
    candidate.files.map((path) => ({
      path,
      side: candidate.repository_side,
      format: FORMAT_LABELS[candidate.format],
    })),
  );
  const formats = [...new Set(files.map((file) => file.format))];
  return (
    <section
      aria-label={t("Files, languages and source details")}
      className="grid min-w-0 gap-5"
    >
      <div className="grid gap-2">
        <h3 className="text-heading font-semibold">
          {t("Files, languages and source details")}
        </h3>
        <p className="text-muted-foreground">
          {files.length} {t(" files · ")}
          {languages.length} {t(" languages ·")} {formats.join(", ")}
        </p>
        <p>
          {t(
            "Choose the base language. All detected languages will be imported.",
          )}
        </p>
      </div>
      <div className="grid gap-2">
        <h4 className="font-medium">{t("Languages to import")}</h4>
        <ul
          aria-label={t("Languages to import")}
          className="flex flex-wrap gap-2"
        >
          {languages.map((language) => (
            <li key={language}>
              <Badge variant="outline">{language}</Badge>
            </li>
          ))}
        </ul>
      </div>
      {job.repository_sides.map((side) => (
        <div key={side.role} className="grid min-w-0 gap-2">
          <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
            <p className="min-w-0 break-words">
              <span className="font-medium">
                {side.role === "keys" ? t("Key files") : t("Translation files")}
              </span>{" "}
              · {side.source_branch}
            </p>
            <Button
              type="button"
              variant="ghost"
              className="font-mono text-xs"
              aria-label={
                job.repository_sides.length === 1
                  ? t("Copy full commit")
                  : t("Copy {{v0}} commit", { v0: side.role })
              }
              onClick={() =>
                void navigator.clipboard?.writeText(side.commit_hash)
              }
            >
              {side.commit_hash.slice(0, 12)}
            </Button>
          </div>
          <div
            // Long file collections scroll locally and remain keyboard accessible.
            role="region"
            aria-label={t("{{v0}} files", { v0: side.role })}
            // eslint-disable-next-line jsx-a11y/no-noninteractive-tabindex
            tabIndex={0}
            className="max-h-72 min-w-0 overflow-y-auto rounded-md border outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <ul className="divide-y">
              {files
                .filter((file) => file.side === side.role)
                .map((file) => (
                  <li
                    key={`${file.side}:${file.path}:${file.format}`}
                    className="flex min-w-0 flex-wrap items-start justify-between gap-2 px-3 py-2"
                  >
                    <span className="min-w-0 flex-1 break-words font-mono text-sm [overflow-wrap:anywhere]">
                      {file.path}
                    </span>
                    <span className="text-xs text-muted-foreground">
                      {file.format}
                    </span>
                  </li>
                ))}
            </ul>
          </div>
        </div>
      ))}
    </section>
  );
}

function BaseLanguageSelect({
  languages,
  hasDefault,
  controlId,
  onValueChange,
  value,
}: {
  languages: readonly string[];
  hasDefault: boolean;
  controlId: string;
  onValueChange: (value: string) => void;
  value: string;
}) {
  useUiLanguage();
  const guidanceId = `${controlId}-guidance`;
  const errorId = `${controlId}-error`;
  const required = value === "";
  const invalid = required || (hasDefault && !isCanonicalBaseLanguage(value));

  return (
    <div className="grid gap-2">
      <Label htmlFor={controlId}>{t("Base language")}</Label>
      {hasDefault ? (
        <Input
          id={controlId}
          className="min-h-[44px] w-full min-w-0 motion-reduce:transition-none"
          value={value}
          onChange={(event) => onValueChange(event.target.value)}
          placeholder={t("For example, en or en-US")}
          autoCapitalize="none"
          spellCheck={false}
          aria-describedby={`${guidanceId}${invalid ? ` ${errorId}` : ""}`}
          aria-invalid={invalid}
        />
      ) : (
        <Select value={value} onValueChange={onValueChange}>
          <SelectTrigger
            id={controlId}
            className="min-h-[44px] w-full min-w-0 motion-reduce:transition-none"
            aria-describedby={`${guidanceId}${required ? ` ${errorId}` : ""}`}
            aria-invalid={required}
          >
            <SelectValue placeholder={t("Select base language")} />
          </SelectTrigger>
          <SelectContent className="motion-reduce:animate-none motion-reduce:transition-none">
            {languages.map((language) => (
              <SelectItem
                key={language}
                value={language}
                className="min-h-[44px] min-w-[44px]"
              >
                {language}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      )}
      <p id={guidanceId} className="text-muted-foreground">
        {hasDefault
          ? t(
              "Enter the language of the default source files, for example en or en-US. All other languages are imported too.",
            )
          : t(
              "Used as the reference language for translation limits. All other languages are imported too.",
            )}
      </p>
      {invalid ? (
        <p id={errorId} className="font-semibold text-warning">
          {required
            ? t("Base language required")
            : t("Enter a canonical language code, for example en or en-US")}
        </p>
      ) : null}
    </div>
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
  useUiLanguage();
  const [announcement, setAnnouncement] = useState("");
  const [baseLanguageChoice, setSelectedBaseLanguage] = useState("");
  const [confirmPending, setConfirmPending] = useState(false);
  const confirmPendingRef = useRef(false);
  const confirmGenerationRef = useRef(0);
  const confirmationErrorRef = useRef<HTMLDivElement>(null);
  const [confirmError, setConfirmError] = useState<
    "base_language_required" | "confirmation_failed" | null
  >(null);
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
  const duplicateSummary = job.duplicate_report_summary;
  const duplicateReportActionable = hasActionableDuplicateReport(job);
  const candidatesAreExact =
    candidates.length > 0 && candidates.every(isExactCandidate);
  const hasMissingBaseLanguage = candidates.some(
    (candidate) =>
      isExactCandidateWithoutLanguage(candidate) &&
      candidate.languages.length === 0,
  );
  const confirmable =
    job.state === "succeeded" &&
    job.is_current &&
    result !== null &&
    candidatesAreExact;
  const languages = detectedLanguages(candidates);
  const hasDefault = hasDefaultLanguage(candidates);
  const selectedBaseLanguage =
    baseLanguageChoice ||
    (!hasDefault && languages.length === 1 ? languages[0]! : "");
  const selectedCandidate = confirmationCandidate(
    candidates,
    selectedBaseLanguage,
  );
  const currentConfirmationIdentity =
    result === null ||
    selectedCandidate === undefined ||
    selectedBaseLanguage === ""
      ? null
      : `${previewJobIdentity(job)}:${result.digest}:${selectedCandidate.id}:${selectedBaseLanguage}`;
  const confirmed =
    currentConfirmationIdentity !== null &&
    confirmedIdentity === currentConfirmationIdentity;

  useEffect(() => {
    if (!confirmed) {
      onConfirmed(false);
    }
  }, [confirmed, onConfirmed]);

  useEffect(
    () => () => {
      confirmGenerationRef.current += 1;
      confirmPendingRef.current = false;
    },
    [],
  );

  useEffect(() => {
    if (confirmError !== null) {
      queueMicrotask(() => confirmationErrorRef.current?.focus());
    }
  }, [confirmError]);

  function invalidateConfirmation() {
    confirmGenerationRef.current += 1;
    confirmPendingRef.current = false;
    setConfirmPending(false);
    setConfirmError(null);
    setConfirmedIdentity(null);
    onConfirmed(false);
  }

  async function submitConfirmation() {
    if (
      confirmPendingRef.current ||
      !confirmable ||
      selectedCandidate === undefined ||
      selectedBaseLanguage === "" ||
      result === null ||
      currentConfirmationIdentity === null
    ) {
      return;
    }
    const generation = ++confirmGenerationRef.current;
    confirmPendingRef.current = true;
    setConfirmPending(true);
    setConfirmError(null);
    try {
      const response = await confirmAdminPreviewJob({
        auth: accessToken,
        body: {
          base_language: selectedBaseLanguage,
          layout_candidate_id: selectedCandidate.id,
          layout_candidate_version: selectedCandidate.version,
          preview_digest: result.digest,
        },
        path: { job_id: job.id },
      });
      if (generation !== confirmGenerationRef.current) {
        return;
      }
      if (response.data === undefined) {
        setConfirmError(
          isBaseLanguageRequired(response.error)
            ? "base_language_required"
            : "confirmation_failed",
        );
        return;
      }
      if (
        !previewConfirmationMatches(
          response.data,
          job,
          selectedCandidate,
          selectedBaseLanguage,
        )
      ) {
        setConfirmError("confirmation_failed");
        return;
      }
      setConfirmedIdentity(currentConfirmationIdentity);
      onConfirmed(true);
    } catch {
      if (generation === confirmGenerationRef.current) {
        setConfirmError("confirmation_failed");
      }
    } finally {
      if (generation === confirmGenerationRef.current) {
        confirmPendingRef.current = false;
        setConfirmPending(false);
      }
    }
  }

  return (
    <div className="grid gap-6">
      <div aria-live="polite" aria-atomic="true" className="sr-only">
        {t(announcement)}
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
            <span>{t("Automatic updates paused")}</span>
            <Button
              type="button"
              variant="outline"
              onClick={() => void refreshStatus()}
            >
              {t("Refresh status")}
            </Button>
          </div>
        ) : null}
      </div>

      {job.state === "queued" || job.state === "running" ? (
        <div className="grid gap-3" role="status">
          <p className="font-medium">{t("Reading files and strings…")}</p>
          <Skeleton className="h-2 w-full" />
        </div>
      ) : null}

      {(job.state === "succeeded" || job.state === "failed") &&
      duplicateReportActionable ? (
        <DuplicateKeysDialog
          key={previewJobIdentity(job)}
          accessToken={accessToken}
          previewJobId={job.id}
        />
      ) : null}

      {pollingError ? (
        <PreviewAlert title={t("Status unavailable")}>
          {t(
            "Automatic updates paused. Refresh status when the connection is available.",
          )}
        </PreviewAlert>
      ) : null}

      {job.state === "timed_out" ? (
        <PreviewAlert title={t("Validation timed out")}>
          <p>
            {t(
              "Validation timed out before the repository could be checked safely.",
            )}
          </p>
          <Button type="button" variant="outline" onClick={onRetry}>
            {t("Retry validation")}
          </Button>
        </PreviewAlert>
      ) : null}

      {job.state === "failed" ? (
        <PreviewAlert title={t("Validation did not complete")}>
          <p>
            {job.diagnostic_code === "repository_scan_limit_reached"
              ? t(
                  "The repository scan limit was reached. Set a narrower localization root in the mapping, then retry validation.",
                )
              : t(
                  "Validation did not complete. Review the reason, then retry.",
                )}
          </p>
          <Button type="button" variant="outline" onClick={onRetry}>
            {t("Retry validation")}
          </Button>
        </PreviewAlert>
      ) : null}

      {job.state === "succeeded" && !job.is_current ? (
        <PreviewAlert title={t("Preview out of date")}>
          {t(
            "This preview no longer matches the current draft. Run validation again.",
          )}
        </PreviewAlert>
      ) : null}

      {job.state === "succeeded" &&
      job.is_current &&
      duplicateReportActionable &&
      duplicateSummary !== null &&
      duplicateSummary !== undefined ? (
        <DuplicateValidationAlert summary={duplicateSummary} />
      ) : null}

      {job.state === "succeeded" &&
      job.is_current &&
      candidates.length === 0 &&
      !duplicateReportActionable ? (
        <PreviewAlert title={t("No supported layout")}>
          {t(
            "No supported localization layout was found in this source branch.",
          )}
        </PreviewAlert>
      ) : null}

      {job.state === "succeeded" &&
      job.is_current &&
      candidates.length > 0 &&
      !candidatesAreExact &&
      !hasMissingBaseLanguage ? (
        <PreviewAlert title={t("Preview cannot be confirmed")}>
          {t(
            "This preview cannot be confirmed. Review the selected repository and branch, then run validation again.",
          )}
        </PreviewAlert>
      ) : null}

      {job.state === "succeeded" && job.is_current && hasMissingBaseLanguage ? (
        <PreviewAlert title={t("Base language required")}>
          {t(
            "No detected language is available for this preview candidate. Run validation again.",
          )}
        </PreviewAlert>
      ) : null}

      {confirmable ? (
        <>
          <SourceDetails candidates={candidates} job={job} />
          <BaseLanguageSelect
            languages={languages}
            hasDefault={hasDefault}
            controlId={`base-language-${job.id}`}
            value={selectedBaseLanguage}
            onValueChange={(value) => {
              setSelectedBaseLanguage(value);
              invalidateConfirmation();
            }}
          />

          <div className="flex flex-wrap items-center gap-3">
            <Button
              type="button"
              disabled={
                selectedCandidate === undefined ||
                selectedBaseLanguage === "" ||
                confirmPending
              }
              aria-busy={confirmPending}
              onClick={() => void submitConfirmation()}
            >
              {t("Confirm preview")}
            </Button>
            {confirmed ? (
              <Badge variant="outline" className="w-fit rounded-md">
                {t("Confirmed")}
              </Badge>
            ) : null}
          </div>
          {confirmError !== null ? (
            <Alert
              ref={confirmationErrorRef}
              tabIndex={-1}
              aria-label={
                confirmError === "base_language_required"
                  ? t("Base language required")
                  : t("Preview not confirmed")
              }
              variant="destructive"
            >
              <AlertTitle>
                {confirmError === "base_language_required"
                  ? t("Base language required")
                  : t("Preview not confirmed")}
              </AlertTitle>
              <AlertDescription>
                {confirmError === "base_language_required"
                  ? t(
                      "The selected base language is no longer available. Choose a detected language and confirm the preview again.",
                    )
                  : t(
                      "This preview no longer matches the current draft. Run validation again.",
                    )}
              </AlertDescription>
            </Alert>
          ) : null}
        </>
      ) : null}
    </div>
  );
}

function sourceName(
  mapping: AdminMappingResponse,
  repositories: readonly AdminRepositoryResponse[],
) {
  const repository = repositories.find(
    (item) => item.id === mapping.primary_repository_id,
  );
  return `${repository?.descriptive_name || repository?.repository_slug || t("Source")} · ${mapping.primary_source_branch}`;
}

function useSourceRepositories(
  accessToken: string,
  mappings: readonly AdminMappingResponse[],
) {
  const key = JSON.stringify([
    accessToken,
    ...new Set(
      mappings.flatMap((mapping) =>
        [
          mapping.primary_repository_id,
          mapping.translations_repository_id,
        ].filter((id): id is string => Boolean(id)),
      ),
    ),
  ]);
  const [result, setResult] = useState<{
    key: string;
    items: AdminRepositoryResponse[];
  }>({ key: "", items: [] });
  useEffect(() => {
    const controller = new AbortController();
    const [, ...ids] = JSON.parse(key) as string[];
    void Promise.all(
      ids.map(async (id) => {
        try {
          const response = await getAdminRepository({
            auth: accessToken,
            path: { repository_id: id },
            signal: controller.signal,
          });
          return response.data?.id === id ? response.data : undefined;
        } catch {
          return undefined;
        }
      }),
    ).then((items) => {
      if (!controller.signal.aborted)
        setResult({
          key,
          items: items.filter(
            (item): item is AdminRepositoryResponse => item !== undefined,
          ),
        });
    });
    return () => controller.abort();
  }, [accessToken, key]);
  return result.key === key ? result.items : [];
}

function MappingPreview({
  accessToken,
  collectionReady,
  sourceName,
  mapping,
  onConfirmed,
  productId,
  revisionId,
  revisionVersion,
}: {
  accessToken: string;
  collectionReady: boolean;
  sourceName: string;
  mapping: AdminMappingResponse;
  onConfirmed: (mappingId: string, confirmed: boolean) => void;
  productId: string;
  revisionId: string;
  revisionVersion: number;
}) {
  useUiLanguage();
  const runGenerationRef = useRef(0);
  const runPendingRef = useRef(false);
  const restoreGenerationRef = useRef(0);
  const [runPending, setRunPending] = useState(false);
  const [runError, setRunError] = useState(false);
  const autoAttemptedRef = useRef(false);
  const [restoreError, setRestoreError] = useState(false);
  const [restoreAttempt, setRestoreAttempt] = useState(0);
  const [restorePending, setRestorePending] = useState(true);
  const [job, setJob] = useState<AdminPreviewJobResponse | null>(null);
  useEffect(
    () => () => {
      runGenerationRef.current += 1;
      restoreGenerationRef.current += 1;
    },
    [],
  );

  useEffect(() => {
    const generation = ++restoreGenerationRef.current;
    queueMicrotask(() => {
      if (generation !== restoreGenerationRef.current) {
        return;
      }
      setJob(null);
      setRestorePending(true);
      setRestoreError(false);
      autoAttemptedRef.current = false;
      void (async () => {
        try {
          const response = await getAdminLatestCandidatePreviewJob({
            auth: accessToken,
            path: { mapping_id: mapping.id, product_id: productId },
          });
          if (generation !== restoreGenerationRef.current) {
            return;
          }
          if (responseStatus(response) === 404) return;
          const restored = response.data;
          if (
            restored === undefined ||
            restored.product_id !== productId ||
            restored.candidate_revision_id !== revisionId ||
            restored.candidate_revision_version !== revisionVersion ||
            restored.mapping_id !== mapping.id
          ) {
            setRestoreError(true);
            return;
          }
          if (!restored.is_current) return;
          setJob(restored);
        } catch {
          if (generation === restoreGenerationRef.current)
            setRestoreError(true);
        } finally {
          if (generation === restoreGenerationRef.current) {
            setRestorePending(false);
          }
        }
      })();
    });
  }, [
    accessToken,
    mapping.id,
    productId,
    revisionId,
    revisionVersion,
    restoreAttempt,
  ]);

  const runValidation = useCallback(async () => {
    if (runPendingRef.current || restorePending || !collectionReady) {
      return;
    }
    const generation = ++runGenerationRef.current;
    runPendingRef.current = true;
    setRunPending(true);
    setRunError(false);
    onConfirmed(mapping.id, false);
    try {
      const commits = await resolveCommits(accessToken, mapping);
      if (generation !== runGenerationRef.current) return;
      const response = await createAdminPreviewJob({
        auth: accessToken,
        body: {
          commits,
          expected_candidate_version: mapping.candidate_version,
        },
        path: { mapping_id: mapping.id, product_id: productId },
      });
      const created = response.data;
      const matchesRequestedAuthority =
        created !== undefined &&
        created.product_id === productId &&
        created.candidate_revision_id === revisionId &&
        created.candidate_revision_version === revisionVersion &&
        created.mapping_id === mapping.id;
      if (generation !== runGenerationRef.current) {
        return;
      }
      if (created === undefined || !matchesRequestedAuthority) {
        setRunError(true);
        return;
      }
      setJob(created);
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
  }, [
    accessToken,
    collectionReady,
    mapping,
    onConfirmed,
    productId,
    restorePending,
    revisionId,
    revisionVersion,
  ]);

  useEffect(() => {
    if (
      !collectionReady ||
      restorePending ||
      restoreError ||
      job !== null ||
      autoAttemptedRef.current
    )
      return;
    let cancelled = false;
    queueMicrotask(() => {
      if (cancelled || autoAttemptedRef.current) return;
      autoAttemptedRef.current = true;
      void runValidation();
    });
    return () => {
      cancelled = true;
    };
  }, [collectionReady, job, restoreError, restorePending, runValidation]);

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
            className="break-words text-heading font-semibold [overflow-wrap:anywhere]"
          >
            {sourceName}
          </h2>
          <p className="text-muted-foreground">
            {mapping.topology === "direct"
              ? t("One repository")
              : t("Separate repositories")}{" "}
            {t("· Source branch: ")}
            {mapping.primary_source_branch}
          </p>
        </div>
        {job !== null && !["queued", "running"].includes(job.state) ? (
          <Button
            type="button"
            variant="outline"
            disabled={runPending || restorePending || !collectionReady}
            aria-busy={runPending}
            onClick={() => void runValidation()}
          >
            {t("Refresh preview")}
          </Button>
        ) : null}
      </div>

      {restoreError ? (
        <PreviewAlert title={t("Preview status unavailable")}>
          <p>
            {t(
              "We could not check the latest analysis. Retry to resume it safely.",
            )}
          </p>
          <Button
            type="button"
            variant="outline"
            onClick={() => setRestoreAttempt((attempt) => attempt + 1)}
          >
            {t("Retry preview status")}
          </Button>
        </PreviewAlert>
      ) : runError ? (
        <PreviewAlert title={t("Validation did not complete")}>
          <p>{t("The source could not be read. Try again.")}</p>
          <Button
            type="button"
            variant="outline"
            disabled={runPending}
            onClick={() => void runValidation()}
          >
            {t("Retry validation")}
          </Button>
        </PreviewAlert>
      ) : null}

      {restorePending ||
      runPending ||
      (job === null && !runError && !restoreError) ? (
        <div className="grid gap-3" role="status" aria-live="polite">
          <p className="font-medium">
            {restorePending
              ? t("Checking source…")
              : t("Reading files and strings…")}
          </p>
          <Skeleton className="h-2 w-full" />
          <p className="text-sm text-muted-foreground">
            {!collectionReady
              ? t("Loading your sources before starting the analysis.")
              : t("The preview will appear here automatically.")}
          </p>
        </div>
      ) : job !== null ? (
        <PreviewJobView
          key={previewJobIdentity(job)}
          accessToken={accessToken}
          initialJob={job}
          onConfirmed={(confirmed) => onConfirmed(mapping.id, confirmed)}
          onRetry={() => void runValidation()}
        />
      ) : null}
    </section>
  );
}

function PublishedMappingRecovery({
  accessToken,
  eligibilityReady,
  sourceName,
  isCurrent,
  mapping,
  onConfirmed,
  productId,
  revisionId,
  revisionVersion,
}: {
  accessToken: string;
  eligibilityReady: boolean;
  sourceName: string;
  isCurrent: boolean;
  mapping: AdminMappingResponse;
  onConfirmed: () => Promise<void>;
  productId: string;
  revisionId: string;
  revisionVersion: number;
}) {
  useUiLanguage();
  const runButtonRef = useRef<HTMLButtonElement>(null);
  const runGenerationRef = useRef(0);
  const runPendingRef = useRef(false);
  const restoreGenerationRef = useRef(0);
  const [announcement, setAnnouncement] = useState("");
  const confirmationErrorRef = useRef<HTMLDivElement>(null);
  const confirmGenerationRef = useRef(0);
  const [confirmError, setConfirmError] = useState<
    "base_language_required" | "confirmation_failed" | null
  >(null);
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
  const [restorePending, setRestorePending] = useState(true);
  const [baseLanguageChoice, setSelectedBaseLanguage] = useState("");
  useEffect(
    () => () => {
      runGenerationRef.current += 1;
      restoreGenerationRef.current += 1;
      confirmGenerationRef.current += 1;
      confirmPendingRef.current = false;
    },
    [],
  );

  useEffect(() => {
    const generation = ++restoreGenerationRef.current;
    queueMicrotask(() => {
      if (generation !== restoreGenerationRef.current) {
        return;
      }
      setJob(null);
      setRestorePending(true);
      void (async () => {
        try {
          const response = await getAdminLatestActiveRevisionRevalidationJob({
            auth: accessToken,
            path: {
              mapping_id: mapping.id,
              product_id: productId,
              revision_id: revisionId,
            },
          });
          if (generation !== restoreGenerationRef.current) {
            return;
          }
          const restored = response.data;
          if (
            restored === undefined ||
            restored.product_id !== productId ||
            restored.active_revision_id !== revisionId ||
            restored.active_revision_version !== revisionVersion ||
            restored.mapping_id !== mapping.id
          ) {
            return;
          }
          setJob(restored);
          const pollingExhausted = activeRevalidationPollingExhausted(restored);
          setPollingError(pollingExhausted);
          setAnnouncement(
            pollingExhausted
              ? "Automatic updates paused. Try again."
              : JOB_LABELS[restored.state],
          );
        } catch {
          // A later visit retries the durable server-side discovery.
        } finally {
          if (generation === restoreGenerationRef.current) {
            setRestorePending(false);
          }
        }
      })();
    });
  }, [accessToken, mapping.id, productId, revisionId, revisionVersion]);

  const result = job?.result ?? null;
  const candidates = result?.layout_candidates ?? [];
  const candidatesAreExact =
    candidates.length > 0 && candidates.every(isExactCandidate);
  const hasMissingBaseLanguage = candidates.some(
    (candidate) =>
      isExactCandidateWithoutLanguage(candidate) &&
      candidate.languages.length === 0,
  );
  const confirmable =
    job?.state === "succeeded" &&
    job.is_current &&
    result !== null &&
    candidatesAreExact;
  const languages = detectedLanguages(candidates);
  const hasDefault = hasDefaultLanguage(candidates);
  const selectedBaseLanguage =
    baseLanguageChoice ||
    (!hasDefault && languages.length === 1 ? languages[0]! : "");
  const selectedCandidate = confirmationCandidate(
    candidates,
    selectedBaseLanguage,
    mapping.selected_layout_candidate_id,
  );
  const currentConfirmationIdentity =
    job === null ||
    result === null ||
    selectedCandidate === undefined ||
    selectedBaseLanguage === ""
      ? null
      : `${activeRevalidationJobIdentity(job)}:${result.digest}:${selectedCandidate.id}:${selectedBaseLanguage}`;
  const confirmed =
    currentConfirmationIdentity !== null &&
    confirmedIdentity === currentConfirmationIdentity;

  const focusRecoveryControl = useCallback(() => {
    queueMicrotask(() => runButtonRef.current?.focus());
  }, []);

  useEffect(() => {
    if (confirmError !== null) {
      queueMicrotask(() => confirmationErrorRef.current?.focus());
    }
  }, [confirmError]);

  function invalidateConfirmation() {
    confirmGenerationRef.current += 1;
    confirmPendingRef.current = false;
    setConfirmPending(false);
    setConfirmError(null);
    setConfirmedIdentity(null);
  }

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
    if (runPendingRef.current || restorePending) {
      return;
    }
    const generation = ++runGenerationRef.current;
    runPendingRef.current = true;
    setRunPending(true);
    setRunError(false);
    setPollingError(false);
    invalidateConfirmation();
    setSelectedBaseLanguage("");
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
      const created = response.data;
      const matchesRequestedAuthority =
        created !== undefined &&
        created.product_id === productId &&
        created.active_revision_id === revisionId &&
        created.active_revision_version === revisionVersion &&
        created.mapping_id === mapping.id;
      if (generation !== runGenerationRef.current) {
        return;
      }
      if (created === undefined || !matchesRequestedAuthority) {
        setAnnouncement("Validation did not complete. Try again.");
        setRunError(true);
        focusRecoveryControl();
        return;
      }
      const pollingExhausted = activeRevalidationPollingExhausted(created);
      setPollingError(pollingExhausted);
      setAnnouncement(
        pollingExhausted
          ? "Automatic updates paused. Try again."
          : JOB_LABELS[created.state],
      );
      setJob(created);
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
      selectedBaseLanguage === "" ||
      currentConfirmationIdentity === null
    ) {
      return;
    }
    const generation = ++confirmGenerationRef.current;
    confirmPendingRef.current = true;
    setConfirmPending(true);
    setConfirmError(null);
    try {
      const response = await confirmAdminActiveRevisionRevalidation({
        auth: accessToken,
        body: {
          active_revision_id: job.active_revision_id,
          active_revision_version: job.active_revision_version,
          base_language: selectedBaseLanguage,
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
      if (generation !== confirmGenerationRef.current) {
        return;
      }
      if (response.data === undefined) {
        setAnnouncement("Preview was not confirmed. Run validation again.");
        setConfirmError(
          isBaseLanguageRequired(response.error)
            ? "base_language_required"
            : "confirmation_failed",
        );
        return;
      }
      if (
        !activeConfirmationMatches(
          response.data,
          job,
          selectedCandidate,
          selectedBaseLanguage,
        )
      ) {
        setAnnouncement("Preview was not confirmed. Run validation again.");
        setConfirmError("confirmation_failed");
        return;
      }
      setConfirmedIdentity(currentConfirmationIdentity);
      setAnnouncement("Confirmed");
      await onConfirmed();
    } catch {
      if (generation === confirmGenerationRef.current) {
        setAnnouncement("Preview was not confirmed. Run validation again.");
        setConfirmError("confirmation_failed");
      }
    } finally {
      if (generation === confirmGenerationRef.current) {
        confirmPendingRef.current = false;
        setConfirmPending(false);
      }
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
        aria-label={t("Active revision recovery status")}
        aria-live="polite"
        aria-atomic="true"
        className="sr-only"
      >
        {t(announcement)}
      </div>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="grid gap-1">
          <h2
            id={`preview-title-${mapping.id}`}
            className="text-heading font-semibold"
          >
            {sourceName}
          </h2>
          <p className="text-muted-foreground">
            {mapping.topology === "direct" ? t("Direct") : t("Separate")}{" "}
            {t(" published mapping")}
          </p>
        </div>
        {eligibilityReady && isCurrent ? (
          <Badge variant="outline" className="w-fit rounded-md">
            {t("Confirmed")}
          </Badge>
        ) : !eligibilityReady ? (
          <Badge variant="outline" className="w-fit rounded-md">
            {t("Checking confirmation")}
          </Badge>
        ) : (
          <Button
            ref={runButtonRef}
            type="button"
            disabled={runPending || restorePending}
            aria-busy={runPending}
            onClick={() => void runValidationAgain()}
          >
            {t("Run validation again")}
          </Button>
        )}
      </div>

      {eligibilityReady && !isCurrent ? (
        <PreviewAlert title={t("Preview out of date")}>
          {t(
            "This preview no longer matches the current draft. Run validation again.",
          )}
        </PreviewAlert>
      ) : null}

      {runError ? (
        <PreviewAlert title={t("Validation did not complete")}>
          {t("Validation did not complete. Try again.")}
        </PreviewAlert>
      ) : null}

      {pollingError ? (
        <PreviewAlert title={t("Status unavailable")}>
          {t("Validation status is unavailable. Try again.")}
        </PreviewAlert>
      ) : null}

      {restorePending && !isCurrent ? (
        <div className="grid gap-2" role="status" aria-live="polite">
          <h3 className="text-heading font-semibold">
            {t("Restoring validation status")}
          </h3>
          <p className="text-muted-foreground">{t("Checking validation…")}</p>
        </div>
      ) : job === null || isCurrent ? null : (
        <div className="grid gap-6">
          <Badge variant="outline" className="w-fit rounded-md">
            {JOB_LABELS[job.state]}
          </Badge>

          {(job.state === "succeeded" || job.state === "failed") &&
          hasActionableDuplicateReport(job) ? (
            <DuplicateKeysDialog
              key={job.id}
              accessToken={accessToken}
              previewJobId={job.id}
            />
          ) : null}

          {job.state === "failed" || job.state === "timed_out" ? (
            <PreviewAlert title={t("Validation did not complete")}>
              {job.diagnostic_code === "repository_scan_limit_reached"
                ? t(
                    "The repository scan limit was reached. Set a narrower localization root in the mapping, then run validation again.",
                  )
                : t("Validation did not complete. Run validation again.")}
            </PreviewAlert>
          ) : null}

          {job.state === "succeeded" && hasMissingBaseLanguage ? (
            <PreviewAlert title={t("Base language required")}>
              {t(
                "No detected language is available for this preview candidate. Run validation again.",
              )}
            </PreviewAlert>
          ) : null}

          {confirmable ? (
            <>
              <SourceDetails candidates={candidates} job={job} />
              <BaseLanguageSelect
                languages={languages}
                hasDefault={hasDefault}
                controlId={`active-base-language-${job.id}`}
                value={selectedBaseLanguage}
                onValueChange={(value) => {
                  setSelectedBaseLanguage(value);
                  invalidateConfirmation();
                }}
              />

              <div className="flex flex-wrap items-center gap-3">
                <Button
                  type="button"
                  disabled={
                    selectedCandidate === undefined ||
                    selectedBaseLanguage === "" ||
                    confirmPending
                  }
                  aria-busy={confirmPending}
                  onClick={() => void submitConfirmation()}
                >
                  {t("Confirm preview")}
                </Button>
                {confirmed ? (
                  <Badge variant="outline" className="w-fit rounded-md">
                    {t("Confirmed")}
                  </Badge>
                ) : null}
              </div>
            </>
          ) : null}

          {confirmError !== null ? (
            <Alert
              ref={confirmationErrorRef}
              tabIndex={-1}
              aria-label={
                confirmError === "base_language_required"
                  ? t("Base language required")
                  : t("Preview not confirmed")
              }
              variant="destructive"
            >
              <AlertTitle>
                {confirmError === "base_language_required"
                  ? t("Base language required")
                  : t("Preview not confirmed")}
              </AlertTitle>
              <AlertDescription>
                {confirmError === "base_language_required"
                  ? t(
                      "The selected base language is no longer available. Choose a detected language and confirm the preview again.",
                    )
                  : t("Preview was not confirmed. Run validation again.")}
              </AlertDescription>
            </Alert>
          ) : null}
        </div>
      )}
    </section>
  );
}

export function ProductPreviewPage({
  accessToken,
  productId,
  embedded = false,
  onProductPublished,
}: ProductPreviewPageProps) {
  useUiLanguage();
  const Heading = embedded ? "h2" : "h1";
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
      const revision = product.candidate_revision ?? product.active_revision;
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

  const repositories = useSourceRepositories(accessToken, collectedMappings);

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
        <Heading
          className={
            embedded
              ? "text-heading font-semibold"
              : "text-display font-semibold"
          }
        >
          {t("Preview and import")}
        </Heading>
        <div className="grid gap-4" role="status" aria-live="polite">
          <Skeleton className="h-8 w-48 max-w-full" />
          <Skeleton className="h-56 w-full" />
          <span>{t("Loading product preview")}</span>
        </div>
      </section>
    );
  }

  if (pageState.status === "error") {
    return (
      <section className="grid gap-6">
        <Heading
          className={
            embedded
              ? "text-heading font-semibold"
              : "text-display font-semibold"
          }
        >
          {t("Preview and import")}
        </Heading>
        <PreviewAlert title={t("Product preview unavailable")}>
          <Button
            type="button"
            variant="outline"
            onClick={() => void loadPage()}
          >
            {t("Retry loading page")}
          </Button>
        </PreviewAlert>
      </section>
    );
  }

  if (mappingCollectionStatus === "loading") {
    return (
      <section className="grid gap-6">
        <Heading
          className={
            embedded
              ? "text-heading font-semibold"
              : "text-display font-semibold"
          }
        >
          {t("Preview and import")}
        </Heading>
        <div className="grid gap-4" role="status" aria-live="polite">
          <Skeleton className="h-8 w-48 max-w-full" />
          <Skeleton className="h-56 w-full" />
          <span>{t("Loading product preview")}</span>
        </div>
      </section>
    );
  }

  if (mappingCollectionStatus === "error") {
    return (
      <section className="grid gap-6">
        <Heading
          className={
            embedded
              ? "text-heading font-semibold"
              : "text-display font-semibold"
          }
        >
          {t("Preview and import")}
        </Heading>
        <PreviewAlert title={t("Product preview unavailable")}>
          <Button
            type="button"
            variant="outline"
            onClick={() => void reloadMappings()}
          >
            {t("Retry loading page")}
          </Button>
        </PreviewAlert>
      </section>
    );
  }

  const mappings = collectedMappings;
  const { product: currentProduct } = pageState;
  const readyState = pageState;
  const collectionReady = mappingCollectionComplete;
  const isPublished =
    currentProduct.is_active && currentProduct.candidate_revision === null;
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
  const publishLabel = t("Import strings");
  const actionLabel = isReactivation ? t("Reactivate product") : publishLabel;
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
      onProductPublished?.(result.data);
      toast.success(
        isReactivation ? t("Product reactivated") : t("Product published"),
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
          <Heading
            className={
              embedded
                ? "text-heading font-semibold"
                : "text-display font-semibold"
            }
          >
            {t("Preview and import")}
          </Heading>
          <p className="break-words text-muted-foreground">
            {isPublished
              ? t(
                  "Follow the import for {{v0}} and open its strings when ready.",
                  { v0: currentProduct.name },
                )
              : isReactivation
                ? t(
                    "Review the confirmed published configuration for {{v0}}.",
                    { v0: currentProduct.name },
                  )
                : t(
                    "We read the sources for {{v0}} automatically. Review the detected files and languages, then choose the base language.",
                    { v0: currentProduct.name },
                  )}
          </p>
        </div>
        <Badge variant="outline" className="w-fit rounded-md">
          {currentProduct.is_active
            ? t("Active")
            : isReactivation
              ? t("Inactive")
              : t("Draft")}
        </Badge>
      </div>

      {isPublished ? (
        <>
          <PublishedMappingImports
            compact
            autoStart
            accessToken={accessToken}
            productId={readyState.productId}
            repositories={repositories}
          />
          <div className="flex flex-wrap gap-3">
            <Button asChild>
              <Link
                to={`/products/${encodeURIComponent(readyState.productId)}/strings`}
              >
                {t("Open product strings")}
              </Link>
            </Button>
            <Button asChild variant="outline">
              <Link
                to={`/admin/products/${encodeURIComponent(readyState.productId)}/edit`}
              >
                {t("Edit configuration")}
              </Link>
            </Button>
          </div>
        </>
      ) : null}

      {!collectionReady && !mappingLoadMoreError ? (
        <Alert aria-label={t("Loading complete mapping set")}>
          <AlertTitle>{t("Loading all mappings")}</AlertTitle>
          <AlertDescription>
            {t("Loading complete mapping set: ")}
            {mappings.length} {mappings.length === 1 ? "mapping" : "mappings"}{" "}
            {t(" loaded.")}
          </AlertDescription>
        </Alert>
      ) : null}

      {mappingLoadMoreError ? (
        <Alert
          variant="destructive"
          aria-label={t("Mapping collection incomplete")}
        >
          <AlertTitle>{t("Mapping collection incomplete")}</AlertTitle>
          <AlertDescription>
            <p>
              {mappings.length} {mappings.length === 1 ? "mapping" : "mappings"}{" "}
              {t(
                "loaded. The complete revision mapping set is required before validation or lifecycle actions are available.",
              )}
            </p>
            <Button
              type="button"
              variant="outline"
              disabled={mappingLoadingMore}
              aria-busy={mappingLoadingMore}
              onClick={() => void loadMoreMappings()}
            >
              {t("Retry loading mappings")}
            </Button>
          </AlertDescription>
        </Alert>
      ) : null}

      {isReactivation && reactivationEligibilityState.status === "error" ? (
        <PreviewAlert title={t("Reactivation status unavailable")}>
          <p>
            {t(
              "The current confirmation state could not be checked. Try again.",
            )}
          </p>
          <Button
            type="button"
            variant="outline"
            onClick={() => void loadReactivationEligibility()}
          >
            {t("Retry confirmation check")}
          </Button>
        </PreviewAlert>
      ) : null}

      {isPublished ? null : collectionReady && mappings.length === 0 ? (
        <Alert>
          <AlertTitle>{t("No mappings configured")}</AlertTitle>
          <AlertDescription>
            <p>{t("Add a translation source before previewing its files.")}</p>
            <Button asChild variant="outline">
              <Link
                to={`/admin/products/${encodeURIComponent(readyState.productId)}/mappings`}
              >
                {t("Configure translation sources")}
              </Link>
            </Button>
          </AlertDescription>
        </Alert>
      ) : (
        mappings.map((mapping) =>
          isReactivation ? (
            <PublishedMappingRecovery
              key={mapping.id}
              accessToken={accessToken}
              eligibilityReady={reactivationEligibility !== null}
              sourceName={sourceName(mapping, repositories)}
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
              sourceName={sourceName(mapping, repositories)}
              mapping={mapping}
              onConfirmed={updateConfirmation}
              productId={readyState.productId}
              revisionId={readyState.revisionId}
              revisionVersion={readyState.revisionVersion}
            />
          ),
        )
      )}

      {publicationError ? (
        <PreviewAlert title={t("Publication did not complete")}>
          {t("The current product configuration remains unchanged. Try again.")}
        </PreviewAlert>
      ) : null}

      {blockers.length > 0 ? (
        <Alert variant="destructive" aria-label={t("Publication blocked")}>
          <AlertTitle>{t("Publication blocked")}</AlertTitle>
          <AlertDescription>
            <ul className="grid gap-2">
              {blockers.map((blocker) => (
                <li key={blocker}>{BLOCKER_LABELS[blocker]}</li>
              ))}
            </ul>
            <ul className="grid gap-2">
              {mappings.map((mapping) => (
                <li key={mapping.id}>
                  <a
                    className="text-accent underline"
                    href={`#preview-${mapping.id}`}
                  >
                    {t("Review ")}
                    {sourceName(mapping, repositories)}
                  </a>
                </li>
              ))}
            </ul>
          </AlertDescription>
        </Alert>
      ) : null}

      {showAction ? (
        <div className="flex flex-wrap items-center justify-between gap-4 border-t pt-6">
          <p className="text-sm text-muted-foreground">
            {allConfirmed
              ? t("Your sources are confirmed and ready to import.")
              : t(
                  "Choose a base language and confirm the sources above to continue.",
                )}
          </p>
          <Button
            type="button"
            className="w-full sm:w-fit"
            disabled={!allConfirmed}
            onClick={() => setPublicationOpen(true)}
          >
            {actionLabel}
          </Button>
        </div>
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
                  ? t("Reactivate {{v0}}?", { v0: currentProduct.name })
                  : t("Import strings for {{v0}}?", {
                      v0: currentProduct.name,
                    })}
              </AlertDialogTitle>
              <AlertDialogDescription>
                {isReactivation
                  ? t("Its confirmed published mappings will resume operating.")
                  : t(
                      "Save this configuration and import strings from {{v0}} confirmed {{v1}}. Progress will appear on this page.",
                      {
                        v0: mappings.length,
                        v1: mappings.length === 1 ? t("source") : t("sources"),
                      },
                    )}
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel disabled={publicationPending}>
                {t("Cancel")}
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
