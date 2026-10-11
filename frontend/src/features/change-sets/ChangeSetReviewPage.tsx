import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import {
  getSubmissionReviewFiles,
  getSubmissionReviewValues,
  type ReviewedFile,
  type SubmissionReviewResponse,
} from "../../api/client";
import { Alert, AlertDescription, AlertTitle } from "../../components/ui/alert";
import { Button } from "../../components/ui/button";
import { Badge } from "../../components/ui/badge";
import { ArrowLeft, GitBranch, GitPullRequest } from "lucide-react";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "../../components/ui/select";
import { useChangeSetWorkspace } from "./changeSetContext";
import { useReviewPolling } from "./useReviewPolling";
import { SubmissionConfirmation } from "./SubmissionConfirmation";

function quantity(count: number, singular: string) {
  return `${count} ${singular}${count === 1 ? "" : "s"}`;
}

export function ChangeSetReviewPage() {
  const heading = useRef<HTMLHeadingElement>(null);
  const {
    accessToken,
    productId,
    selection,
    destinations,
    targets,
    review,
    setReview,
    busy,
    error,
    requestReview,
    canRequest,
    readUnavailable,
    readSignal,
    revokeRead,
  } = useChangeSetWorkspace();
  useEffect(() => {
    heading.current?.focus({ preventScroll: true });
  }, [readUnavailable]);
  const polling = useReviewPolling(
    accessToken,
    productId,
    review,
    setReview,
    revokeRead,
    readSignal,
  );
  const relevant = (
    review?.destinations?.length ? review.destinations : destinations
  ).filter((destination) =>
    selection.some(
      (entry) => entry.candidate.mapping_id === destination.mapping_id,
    ),
  );
  const groups = review?.groups ?? [];
  const back = `/products/${encodeURIComponent(productId)}/change-sets`;
  if (readUnavailable)
    return (
      <section className="grid gap-(--space-md)">
        <h2 ref={heading} tabIndex={-1} className="text-heading font-semibold">
          Review unavailable
        </h2>
        <p>This review is unavailable to your account.</p>
        <Button asChild variant="outline" className="w-fit">
          <Link to={back}>Back to selection</Link>
        </Button>
      </section>
    );
  if (!selection.length)
    return (
      <section className="grid gap-(--space-md)">
        <h2 ref={heading} tabIndex={-1} className="text-heading font-semibold">
          No changes selected
        </h2>
        <p>Select approved changes to prepare a review.</p>
        <Button asChild variant="outline" className="w-fit">
          <Link to={back}>Back to selection</Link>
        </Button>
      </section>
    );
  return (
    <section
      aria-labelledby="review-heading"
      className="grid min-w-0 gap-(--space-lg)"
    >
      <div className="flex min-w-0 flex-wrap items-center justify-between gap-3">
        <h2
          ref={heading}
          tabIndex={-1}
          id="review-heading"
          className="text-heading font-semibold"
        >
          {groups.length > 1 ? "Review change sets" : "Review change set"}
        </h2>
        <Button asChild variant="outline" className="w-fit">
          <Link to={back}>
            <ArrowLeft aria-hidden="true" className="size-4" />
            Back to selection
          </Link>
        </Button>
      </div>
      <section aria-label="Included proposals">
        <details className="rounded-lg border bg-card px-4">
          <summary className="cursor-pointer py-3 font-medium">
            {quantity(selection.length, "selected change")}
            {selection.some((entry) => entry.needsReview) && (
              <span className="ml-2 text-destructive">Needs review</span>
            )}
          </summary>
          <ul className="space-y-2 pb-4 text-sm">
            {selection.map((entry) => (
              <li className="wrap-anywhere" key={entry.candidate.proposal_id}>
                {entry.candidate.key} ({entry.candidate.language}) · Version{" "}
                {entry.candidate.version}
                {entry.needsReview ? " · Needs review" : ""}
              </li>
            ))}
          </ul>
        </details>
      </section>
      {relevant.length > 0 && (
        <section
          className="grid min-w-0 gap-3"
          aria-label="Permitted destinations"
        >
          <h3 className="font-semibold">Destination</h3>
          {relevant.map((destination) => {
            const chosen =
              targets.find(
                (target) => target.mapping_id === destination.mapping_id,
              )?.target_branch ?? destination.chosen_target;
            const label = `Target branch for ${destination.workspace}/${destination.repository_slug} (${destination.mapping_id})`;
            return (
              <div
                key={destination.mapping_id}
                className="grid min-w-0 gap-3 rounded-lg border bg-card p-4 sm:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]"
              >
                <div className="min-w-0">
                  <p className="mb-1 text-sm text-muted-foreground">
                    Repository
                  </p>
                  <p className="font-semibold wrap-anywhere">
                    {destination.workspace}/{destination.repository_slug}
                  </p>
                </div>
                <div className="min-w-0">
                  <p className="mb-1 flex items-center gap-1.5 text-sm text-muted-foreground">
                    <GitBranch aria-hidden="true" className="size-4" />
                    Target branch
                  </p>
                  {!canRequest || destination.allowed_targets.length === 1 ? (
                    <p className="font-mono text-sm wrap-anywhere">{chosen}</p>
                  ) : (
                    <Select
                      value={chosen}
                      onValueChange={(target_branch) => {
                        void requestReview([
                          ...targets.filter(
                            (target) =>
                              target.mapping_id !== destination.mapping_id,
                          ),
                          { mapping_id: destination.mapping_id, target_branch },
                        ]);
                      }}
                    >
                      <SelectTrigger
                        aria-label={label}
                        className="mt-(--space-sm) min-h-[44px] w-full max-w-full items-start text-left data-[size=default]:h-auto *:data-[slot=select-value]:min-w-0 *:data-[slot=select-value]:flex-1 *:data-[slot=select-value]:line-clamp-none *:data-[slot=select-value]:block *:data-[slot=select-value]:wrap-anywhere *:data-[slot=select-value]:whitespace-normal"
                      >
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {destination.allowed_targets.map((branch) => (
                          <SelectItem key={branch} value={branch}>
                            {branch}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  )}
                </div>
              </div>
            );
          })}
        </section>
      )}
      <p role="status" className="text-sm text-muted-foreground">
        {busy || review?.state === "queued" || review?.state === "running"
          ? "Checking selected changes…"
          : review?.state === "ready"
            ? "Review ready"
            : review?.state === "accepted"
              ? "Review accepted"
              : review?.state === "expired"
                ? "Review expired"
                : review?.state === "failed" || error
                  ? "Review could not be prepared"
                  : "Review not prepared"}
      </p>
      {error && (
        <Alert variant="destructive">
          <AlertTitle>Selected changes need review</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}
      {review?.error_code && (
        <Alert variant="destructive">
          <AlertTitle>Selected changes need review</AlertTitle>
          <AlertDescription>
            {review.error_code.replaceAll("_", " ")}. Refresh and review the
            selected changes.
          </AlertDescription>
        </Alert>
      )}
      {polling.error && <p role="alert">Status could not be refreshed</p>}
      {polling.paused && <p>Automatic updates paused</p>}
      {(polling.error || polling.paused) && (
        <Button className="w-fit" variant="outline" onClick={polling.refresh}>
          Refresh status
        </Button>
      )}
      {canRequest &&
        !busy &&
        (!review ||
          review.state === "failed" ||
          review.state === "expired") && (
          <Button
            className="w-fit"
            disabled={selection.some((entry) => entry.needsReview)}
            onClick={() => void requestReview()}
          >
            Check selected changes again
          </Button>
        )}
      {(review?.state === "ready" || review?.state === "accepted") && (
        <ReadyReview
          key={`${review.id}:${review.attempt}:${review.manifest_digest}`}
          review={review}
          accessToken={accessToken}
          productId={productId}
        />
      )}
    </section>
  );
}

function ReadyReview({
  review,
  accessToken,
  productId,
}: {
  review: SubmissionReviewResponse;
  accessToken: string;
  productId: string;
}) {
  const { readSignal, revokeRead } = useChangeSetWorkspace();
  const [files, setFiles] = useState<ReviewedFile[]>([]);
  const [values, setValues] = useState(review.values);
  const [nextFile, setNextFile] = useState<number | null>(0);
  const [nextValue, setNextValue] = useState<number | null>(
    review.next_values_after ?? null,
  );
  const [fileLoading, setFileLoading] = useState(false);
  const [valueLoading, setValueLoading] = useState(false);
  const [fileError, setFileError] = useState(false);
  const [valueError, setValueError] = useState(false);
  const fileController = useRef<AbortController | null>(null);
  const valueController = useRef<AbortController | null>(null);
  const generation = useRef(0);
  useEffect(() => {
    const expected = ++generation.current;
    const controller = new AbortController();
    fileController.current = controller;
    const signal = AbortSignal.any([controller.signal, readSignal]);
    void getSubmissionReviewFiles({
      auth: accessToken,
      path: { product_id: productId, review_id: review.id },
      query: { after: 0 },
      signal,
    })
      .then(({ data, response }) => {
        if (signal.aborted || generation.current !== expected) return;
        if ([401, 403, 404].includes(response?.status ?? 0)) {
          revokeRead();
          return;
        }
        if (!data) throw new Error("unavailable");
        setFiles(data.items);
        setNextFile(data.next_after);
      })
      .catch(() => {
        if (!signal.aborted && generation.current === expected)
          setFileError(true);
      });
    return () => {
      generation.current = expected + 1;
      fileController.current?.abort();
      valueController.current?.abort();
    };
  }, [accessToken, productId, review.id, readSignal, revokeRead]);
  async function loadFiles() {
    if (nextFile === null || fileLoading) return;
    fileController.current?.abort();
    const request = new AbortController();
    fileController.current = request;
    const signal = AbortSignal.any([request.signal, readSignal]);
    const expected = generation.current;
    setFileLoading(true);
    try {
      const { data, response } = await getSubmissionReviewFiles({
        auth: accessToken,
        path: { product_id: productId, review_id: review.id },
        query: { after: nextFile },
        signal,
      });
      if (signal.aborted || generation.current !== expected) return;
      if ([401, 403, 404].includes(response?.status ?? 0)) {
        revokeRead();
        return;
      }
      if (!data) throw new Error("unavailable");
      setFiles((current) => [
        ...current.filter(
          (file) => !data.items.some((next) => next.index === file.index),
        ),
        ...data.items,
      ]);
      setNextFile(data.next_after);
      setFileError(false);
    } catch {
      if (!signal.aborted && generation.current === expected)
        setFileError(true);
    } finally {
      if (!signal.aborted && generation.current === expected)
        setFileLoading(false);
    }
  }
  async function loadValues() {
    if (nextValue === null || valueLoading) return;
    valueController.current?.abort();
    const request = new AbortController();
    valueController.current = request;
    const signal = AbortSignal.any([request.signal, readSignal]);
    const expected = generation.current;
    setValueLoading(true);
    try {
      const { data, response } = await getSubmissionReviewValues({
        auth: accessToken,
        path: { product_id: productId, review_id: review.id },
        query: { after: nextValue },
        signal,
      });
      if (signal.aborted || generation.current !== expected) return;
      if ([401, 403, 404].includes(response?.status ?? 0)) {
        revokeRead();
        return;
      }
      if (!data) throw new Error("unavailable");
      setValues((current) => [...current, ...data.items]);
      setNextValue(data.next_after);
      setValueError(false);
    } catch {
      if (!signal.aborted && generation.current === expected)
        setValueError(true);
    } finally {
      if (!signal.aborted && generation.current === expected)
        setValueLoading(false);
    }
  }
  const groups = review.groups ?? [];
  return (
    <section
      aria-label="Selected changes review"
      className="grid min-w-0 gap-(--space-lg)"
    >
      <div
        aria-label="Review totals"
        className="flex flex-wrap items-center gap-2"
      >
        <Badge variant="secondary">
          {quantity(review.proposal_count ?? 0, "change")}
        </Badge>
        <Badge variant="secondary">
          {quantity(review.value_count ?? 0, "translation")}
        </Badge>
        <Badge variant="secondary">
          {quantity(review.file_count ?? 0, "file")}
        </Badge>
        <Badge variant="outline">
          <GitPullRequest aria-hidden="true" className="size-3.5" />
          {quantity(groups.length, "pull request")}
        </Badge>
      </div>
      {groups.length > 1 && (
        <section
          aria-label="Pull requests"
          className="grid min-w-0 gap-2 rounded-lg border bg-card p-4"
        >
          <h3 className="font-semibold">Pull requests</h3>
          {groups.map((group) => (
            <p key={group.id} className="text-sm wrap-anywhere">
              <span className="font-medium">
                {group.workspace}/{group.repository_slug}
              </span>{" "}
              → <code>{group.target_branch}</code>
            </p>
          ))}
        </section>
      )}
      <section
        aria-label="Value changes"
        className="grid min-w-0 gap-(--space-md)"
      >
        <h3 className="font-semibold">Translation changes</h3>
        {values.map((value, index) => (
          <article
            key={`${value.group_id}:${value.value_id}:${index}`}
            className="min-w-0 overflow-hidden rounded-lg border bg-card"
          >
            <header className="grid min-w-0 gap-2 border-b bg-muted/30 px-4 py-3">
              <div className="flex min-w-0 flex-wrap items-center gap-2">
                <h4 className="min-w-0 flex-1 font-mono font-semibold wrap-anywhere">
                  {value.key ?? ""}
                </h4>
                <Badge variant="outline" className="shrink-0">
                  {value.language}
                </Badge>
                {value.selector && value.selector_kind !== "scalar" && (
                  <Badge
                    variant="secondary"
                    className="max-w-full whitespace-normal wrap-anywhere"
                  >
                    {value.selector}
                  </Badge>
                )}
              </div>
              <p className="text-sm text-muted-foreground wrap-anywhere">
                {value.file_path}
              </p>
            </header>
            <div className="grid min-w-0 sm:grid-cols-2">
              <div className="min-w-0 border-b bg-muted/20 p-4 sm:border-r sm:border-b-0">
                <p className="mb-2 text-sm font-medium text-muted-foreground">
                  Current
                </p>
                <p
                  lang={value.language}
                  dir="auto"
                  className="whitespace-pre-wrap wrap-anywhere"
                >
                  {value.published_text || (
                    <span className="italic text-muted-foreground">Empty</span>
                  )}
                </p>
              </div>
              <div className="min-w-0 bg-emerald-50/60 p-4 dark:bg-emerald-950/20">
                <p className="mb-2 text-sm font-semibold text-emerald-800 dark:text-emerald-300">
                  Proposed
                </p>
                <p
                  lang={value.language}
                  dir="auto"
                  className="whitespace-pre-wrap wrap-anywhere"
                >
                  {value.proposed_text || (
                    <span className="italic text-muted-foreground">Empty</span>
                  )}
                </p>
                {value.effective_maximum != null &&
                  value.character_count != null && (
                    <p
                      className={`mt-3 text-sm ${value.character_count > value.effective_maximum ? "font-semibold text-destructive" : "text-muted-foreground"}`}
                    >
                      {value.character_count} / {value.effective_maximum}{" "}
                      characters
                      {value.character_count > value.effective_maximum
                        ? " · Over limit"
                        : ""}
                    </p>
                  )}
              </div>
            </div>
          </article>
        ))}
        {valueError && (
          <p role="alert">
            Diff entries could not be loaded. Retry to inspect the complete
            review.
          </p>
        )}
        {nextValue !== null && (
          <Button
            className="w-fit"
            variant="outline"
            disabled={valueLoading}
            onClick={() => void loadValues()}
          >
            {valueLoading ? "Loading diff entries…" : "Load more diff entries"}
          </Button>
        )}
      </section>
      <section
        aria-label="File changes"
        className="grid min-w-0 gap-(--space-md)"
      >
        <h3 className="font-semibold">File changes</h3>
        {files.map((file) => (
          <article
            key={file.index}
            className="min-w-0 rounded-lg border bg-card p-4"
          >
            <h4 className="font-medium wrap-anywhere">{file.path}</h4>
            <p className="text-sm wrap-anywhere">
              {quantity(file.changed_values, "changed translation")}
              {groups.length > 1 && (
                <>
                  {" "}
                  ·{" "}
                  {
                    groups.find((group) => group.id === file.group_id)
                      ?.repository_slug
                  }
                </>
              )}
            </p>
            <details>
              <summary className="cursor-pointer min-h-[44px]">
                File preservation hashes
              </summary>
              <p className="wrap-anywhere">Before: {file.before_sha256}</p>
              <p className="wrap-anywhere">After: {file.after_sha256}</p>
            </details>
          </article>
        ))}
        {fileError && (
          <p role="alert">
            Files could not be loaded. Retry to inspect the complete review.
          </p>
        )}
        {nextFile !== null && (
          <Button
            className="w-fit"
            variant="outline"
            disabled={fileLoading}
            onClick={() => void loadFiles()}
          >
            {fileLoading ? "Loading files…" : "Load more files"}
          </Button>
        )}
      </section>
      <details className="min-w-0 rounded-lg border bg-card px-4">
        <summary className="cursor-pointer py-3 font-medium">
          Technical details
        </summary>
        <div className="grid min-w-0 gap-4 pb-4">
          {groups.map((group) => (
            <article
              key={group.id}
              className="min-w-0 rounded-lg border p-(--space-md)"
            >
              <h3 className="font-semibold wrap-anywhere">
                {group.workspace}/{group.repository_slug} →{" "}
                {group.target_branch}
              </h3>
              <p className="text-sm wrap-anywhere">
                Repository {group.repository_id} · Group {group.id}
              </p>
              <p>
                {quantity(group.proposal_ids.length, "proposal")} ·{" "}
                {quantity(group.value_count, "value")} ·{" "}
                {quantity(group.file_count, "file")}
              </p>
              <dl className="grid gap-(--space-sm) mt-(--space-md)">
                <div>
                  <dt className="font-medium">Pull request source branch</dt>
                  <dd className="wrap-anywhere">{group.source_branch}</dd>
                </div>
                <div>
                  <dt className="font-medium">Target branch</dt>
                  <dd className="wrap-anywhere">
                    {group.target_branch} · {group.target_head}
                  </dd>
                </div>
                {group.sources.map((source, index) => (
                  <div
                    key={`${source.mapping_id}:${source.repository_side}:${index}`}
                  >
                    <dt className="font-medium">
                      Imported source · {source.repository_side}
                    </dt>
                    <dd className="wrap-anywhere">
                      {source.branch} · {source.commit_hash}
                      <br />
                      Repository {source.repository_id} · Mapping{" "}
                      {source.mapping_id}
                    </dd>
                  </div>
                ))}
              </dl>
            </article>
          ))}
        </div>
      </details>
      <SubmissionConfirmation review={review} />
    </section>
  );
}
