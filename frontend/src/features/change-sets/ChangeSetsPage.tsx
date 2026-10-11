import { useContext, useEffect, useRef, useState } from "react";
import {
  useNavigate,
  useParams,
  useSearchParams,
  useLocation,
} from "react-router-dom";
import {
  getChangeSetCandidates,
  type ChangeSetCandidate,
  type ChangeSetCandidatesResponse,
  type GetChangeSetCandidatesData,
} from "../../api/client";
import { Alert, AlertDescription, AlertTitle } from "../../components/ui/alert";
import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { Checkbox } from "../../components/ui/checkbox";
import { Input } from "../../components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "../../components/ui/select";
import { ChangeSetWorkspace } from "./ChangeSetWorkspace";
import { ChangeSetContext, useChangeSetWorkspace } from "./changeSetContext";
import { ChangeSetHistory } from "./ChangeSetHistory";
import { consumeSubmissionEntry, peekSubmissionEntry } from "./submissionEntry";
type Filters = NonNullable<GetChangeSetCandidatesData["query"]>;
export function ChangeSetsPage({ accessToken }: { accessToken: string }) {
  const context = useContext(ChangeSetContext);
  const productId = useParams<"productId">().productId ?? "";
  return context ? (
    <WorkspaceTabs />
  ) : (
    <ChangeSetWorkspace
      key={`${accessToken}:${productId}`}
      accessToken={accessToken}
      productId={productId}
    >
      <WorkspaceTabs />
    </ChangeSetWorkspace>
  );
}
function WorkspaceTabs() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const { productId } = useChangeSetWorkspace();
  const location = useLocation();
  const history =
    params.get("tab") === "history" || location.pathname.endsWith("/history");
  return (
    <div className="grid min-w-0 gap-(--space-lg)">
      <nav
        aria-label="Change set views"
        className="flex flex-wrap gap-(--space-sm)"
      >
        <Button
          variant={history ? "outline" : "default"}
          aria-current={!history ? "page" : undefined}
          onClick={() =>
            navigate(`/products/${encodeURIComponent(productId)}/change-sets`)
          }
        >
          Pending changes
        </Button>
        <Button
          variant={history ? "default" : "outline"}
          aria-current={history ? "page" : undefined}
          onClick={() =>
            navigate(
              `/products/${encodeURIComponent(productId)}/change-sets/history`,
            )
          }
        >
          Submission history
        </Button>
      </nav>
      {history ? <ChangeSetHistory /> : <CandidateList />}
    </div>
  );
}
function CandidateList() {
  const {
    accessToken,
    productId,
    observe,
    selection,
    select,
    remove,
    limit,
    canRequest,
    error,
    requestReview,
    principalId,
    candidateMemory,
    setCandidateMemory,
    returnFocus,
    setReturnFocus,
    revokeRead,
  } = useChangeSetWorkspace();
  const navigate = useNavigate();
  const [entry] = useState(() =>
    peekSubmissionEntry({ principalId, accessToken, productId }),
  );
  useEffect(() => {
    consumeSubmissionEntry({ principalId, accessToken, productId });
  }, [principalId, accessToken, productId]);
  const seeded = useRef(false);
  const [entryError, setEntryError] = useState(false);
  const [unavailable, setUnavailable] = useState(false);
  const heading = useRef<HTMLHeadingElement>(null);
  const [filters, setFilters] = useState<Filters>(
    entry
      ? { state: "all", translation_group_id: entry.translationGroupId }
      : (candidateMemory?.filters ?? {
          state: "approved",
          query: "",
          language: "",
        }),
  );
  const [query, setQuery] = useState(filters.query ?? "");
  const [language, setLanguage] = useState(filters.language ?? "");
  const [after, setAfter] = useState<string>();
  const [reload, setReload] = useState(0);
  const [result, setResult] = useState<
    | {
        key: string;
        page: ChangeSetCandidatesResponse;
        items: ChangeSetCandidate[];
      }
    | undefined
  >(
    !entry && candidateMemory
      ? {
          key: JSON.stringify(candidateMemory.filters),
          page: candidateMemory.page,
          items: candidateMemory.items,
        }
      : undefined,
  );
  const [failure, setFailure] = useState<string>();
  const filterKey = JSON.stringify(filters);
  const current = result?.key === filterKey ? result : undefined;
  const items = current?.items ?? [];
  const selectRef = useRef(select);
  useEffect(() => {
    selectRef.current = select;
  }, [select]);
  useEffect(() => {
    if (!current) return;
    setCandidateMemory({ filters, items: current.items, page: current.page });
  }, [current, filters, setCandidateMemory]);
  useEffect(() => {
    if (!current) return;
    const target = returnFocus
      ? document.getElementById(returnFocus)
      : heading.current;
    (target ?? heading.current)?.focus({ preventScroll: true });
    if (returnFocus) setReturnFocus(undefined);
    // Focus only on the first loaded projection after route entry.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [!!current]);
  useEffect(() => {
    const controller = new AbortController();
    void getChangeSetCandidates({
      auth: accessToken,
      path: { product_id: productId },
      query: { ...filters, after },
      signal: controller.signal,
    })
      .then(({ data, response }) => {
        if (controller.signal.aborted) return;
        if ([401, 403, 404].includes(response?.status ?? 0)) {
          setResult(undefined);
          setUnavailable(true);
          revokeRead();
          return;
        }
        if (!data) throw new Error("unavailable");
        observe(data);
        if (entry && !seeded.current) {
          seeded.current = true;
          const exact = data.items.length === 1 ? data.items[0] : undefined;
          if (exact?.can_review && exact.version === entry.expectedVersion)
            selectRef.current([exact]);
          else setEntryError(true);
        }
        setResult((previous) => ({
          key: filterKey,
          page: data,
          items:
            after && previous?.key === filterKey
              ? [
                  ...previous.items.filter(
                    (item) =>
                      !data.items.some(
                        (next) => next.proposal_id === item.proposal_id,
                      ),
                  ),
                  ...data.items,
                ]
              : data.items,
        }));
        setFailure(undefined);
      })
      .catch(() => {
        if (!controller.signal.aborted) setFailure(filterKey);
      });
    return () => controller.abort();
  }, [
    accessToken,
    productId,
    observe,
    filters,
    filterKey,
    after,
    reload,
    entry,
    revokeRead,
  ]);
  const selectedIds = new Set(
    selection.map((entry) => entry.candidate.proposal_id),
  );
  const eligible = items.filter((item) => item.can_review);
  const allLoaded =
    eligible.length > 0 &&
    eligible.every((item) => selectedIds.has(item.proposal_id));
  const someLoaded = eligible.some((item) => selectedIds.has(item.proposal_id));
  const outside = selection.filter(
    (entry) =>
      !items.some((item) => item.proposal_id === entry.candidate.proposal_id),
  ).length;
  function updateFilters(next: Filters) {
    setAfter(undefined);
    setFilters(next);
  }
  if (unavailable)
    return (
      <Alert>
        <AlertTitle>Change set unavailable</AlertTitle>
        <AlertDescription>
          This product's changes are unavailable to your account.
        </AlertDescription>
      </Alert>
    );
  return (
    <section
      className="grid min-w-0 gap-(--space-lg)"
      aria-labelledby="change-sets-heading"
    >
      <div>
        <h2
          ref={heading}
          tabIndex={-1}
          id="change-sets-heading"
          className="text-heading font-semibold"
        >
          Change sets
        </h2>
        <p className="text-muted-foreground">
          Select approved changes to prepare a pull request.
        </p>
      </div>
      {entryError && (
        <Alert>
          <AlertTitle>Selected changes need review</AlertTitle>
          <AlertDescription>
            The saved proposal changed or is no longer eligible. Review the
            current version before selecting it.
          </AlertDescription>
        </Alert>
      )}
      <form
        className="grid gap-(--space-md) sm:grid-cols-3"
        onSubmit={(event) => {
          event.preventDefault();
          updateFilters({ ...filters, query, language });
        }}
      >
        <label htmlFor="change-query">
          Search changes
          <Input
            id="change-query"
            value={query}
            maxLength={256}
            onChange={(event) => setQuery(event.target.value)}
          />
        </label>
        <label htmlFor="change-language">
          Language
          <Input
            id="change-language"
            value={language}
            maxLength={64}
            onChange={(event) => setLanguage(event.target.value)}
            placeholder="All languages"
          />
        </label>
        <div>
          <label id="proposal-state-label" htmlFor="proposal-state">
            Proposal state
          </label>
          <Select
            value={filters.state}
            onValueChange={(value) => {
              if (
                value === "approved" ||
                value === "draft" ||
                value === "rejected" ||
                value === "all"
              )
                updateFilters({ ...filters, state: value });
            }}
          >
            <SelectTrigger
              id="proposal-state"
              aria-labelledby="proposal-state-label"
              className="min-h-[44px] w-full"
            >
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="approved">Approved</SelectItem>
              <SelectItem value="all">All pending</SelectItem>
              <SelectItem value="draft">Draft</SelectItem>
              <SelectItem value="rejected">Rejected</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <Button type="submit" variant="outline" className="w-fit">
          Apply filters
        </Button>
        <Button
          type="button"
          variant="ghost"
          className="w-fit"
          onClick={() => {
            setQuery("");
            setLanguage("");
            updateFilters({ state: "approved", query: "", language: "" });
          }}
        >
          Clear filters
        </Button>
      </form>
      <p className="text-sm text-muted-foreground">
        Showing {filters.state === "all" ? "all pending" : filters.state}{" "}
        changes{filters.query ? ` matching “${filters.query}”` : ""}
        {filters.language ? ` in ${filters.language}` : ""}.
      </p>
      {failure === filterKey && (
        <Alert variant="destructive">
          <AlertTitle>Pending changes could not be loaded</AlertTitle>
          <AlertDescription>
            <Button
              variant="outline"
              onClick={() => setReload((value) => value + 1)}
            >
              Retry loading changes
            </Button>
          </AlertDescription>
        </Alert>
      )}
      {!current && failure !== filterKey && (
        <p role="status">Loading approved changes…</p>
      )}
      {current && !canRequest && (
        <Alert>
          <AlertTitle>Submission access is read-only</AlertTitle>
          <AlertDescription>
            An admin or reviewer can submit approved changes. You can inspect
            changes and submission history.
          </AlertDescription>
        </Alert>
      )}
      {current && !items.length && (
        <div>
          <h3 className="font-semibold">
            {filters.query ||
            filters.language ||
            filters.state !== "approved" ||
            filters.translation_group_id
              ? "No changes match these filters"
              : "No approved changes ready"}
          </h3>
          <p>
            {filters.query ||
            filters.language ||
            filters.state !== "approved" ||
            filters.translation_group_id
              ? "Clear filters to see the product's pending changes."
              : "Approve complete pending changes before creating a pull request. You can view other proposal states or return to Strings."}
          </p>
        </div>
      )}
      {canRequest && (
        <label
          htmlFor="select-loaded-changes"
          className="flex min-h-[44px] items-center gap-(--space-md)"
        >
          <Checkbox
            id="select-loaded-changes"
            aria-label="Select loaded eligible changes"
            checked={allLoaded ? true : someLoaded ? "indeterminate" : false}
            disabled={!eligible.length}
            onCheckedChange={(checked) => {
              if (checked) select(eligible);
              else for (const item of eligible) remove(item.proposal_id);
            }}
          />
          Select loaded eligible changes
        </label>
      )}
      <ul className="grid gap-(--space-md)" aria-label="Pending changes">
        {items.map((item) => (
          <li
            key={item.proposal_id}
            className="min-w-0 rounded-lg border p-(--space-md)"
          >
            <label
              htmlFor={`select-change-${item.proposal_id}`}
              className="flex min-h-[44px] items-center gap-(--space-md)"
            >
              {canRequest && (
                <Checkbox
                  id={`select-change-${item.proposal_id}`}
                  checked={selectedIds.has(item.proposal_id)}
                  disabled={
                    !item.can_review && !selectedIds.has(item.proposal_id)
                  }
                  aria-label={`Select ${item.key} (${item.language})`}
                  onCheckedChange={(checked) =>
                    checked ? select([item]) : remove(item.proposal_id)
                  }
                />
              )}
              <span className="min-w-0 flex-1 wrap-anywhere">
                {item.key} ({item.language})
              </span>
              <Badge variant="outline">{item.state}</Badge>
            </label>
            <p className="text-sm text-muted-foreground">
              Version {item.version} · {item.value_count} values
            </p>
            <p
              className="wrap-anywhere whitespace-pre-wrap"
              lang={item.language}
              dir="auto"
            >
              <span className="font-semibold">Published: </span>
              {item.published_excerpt}
            </p>
            <p
              className="wrap-anywhere whitespace-pre-wrap"
              lang={item.language}
              dir="auto"
            >
              <span className="font-semibold">Proposed: </span>
              {item.proposed_excerpt}
            </p>
            {item.blocker && (
              <p className="mt-(--space-sm) text-sm">
                Selected changes need review:{" "}
                {item.blocker.replaceAll("_", " ")}.
              </p>
            )}
          </li>
        ))}
      </ul>
      {current?.page.next_after && (
        <Button
          className="w-fit"
          variant="outline"
          onClick={() => setAfter(current.page.next_after ?? undefined)}
        >
          Load more changes
        </Button>
      )}
      {selection.length > 0 && (
        <section
          aria-label="Selected changes"
          className="grid gap-(--space-sm)"
        >
          <h3 className="font-semibold">
            {selection.length} selected · {outside} outside current filters
          </h3>
          {selection.map((entry) => (
            <div
              key={entry.candidate.proposal_id}
              className="flex flex-wrap items-center gap-(--space-sm)"
            >
              <span className="min-w-0 wrap-anywhere">
                {entry.candidate.key} ({entry.candidate.language}), version{" "}
                {entry.candidate.version}
                {entry.needsReview
                  ? " — Needs review: remove and select the current version."
                  : ""}
              </span>
              <Button
                variant="ghost"
                onClick={() => remove(entry.candidate.proposal_id)}
                aria-label={`Remove ${entry.candidate.key} (${entry.candidate.language})`}
              >
                Remove
              </Button>
            </div>
          ))}
        </section>
      )}
      {canRequest && (
        <>
          <p className="text-sm text-muted-foreground">
            Select at most {limit} complete proposals.
          </p>
          <Button
            id="review-selected-changes"
            className="w-fit"
            disabled={
              !selection.length || selection.some((entry) => entry.needsReview)
            }
            onClick={() => {
              setReturnFocus("review-selected-changes");
              void requestReview();
              navigate(
                `/products/${encodeURIComponent(productId)}/change-sets/review`,
              );
            }}
          >
            Review selected changes ({selection.length})
          </Button>
        </>
      )}
      {error && (
        <Alert variant="destructive">
          <AlertTitle>Selected changes need review</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}
    </section>
  );
}
