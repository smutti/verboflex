import { statusLabel } from "@/i18n/statusLabels";
import { t, useUiLanguage } from "@/i18n";
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
import { BranchWorkflowPanel } from "./BranchWorkflowPanel";
import { consumeSubmissionEntry, peekSubmissionEntry } from "./submissionEntry";
type Filters = NonNullable<GetChangeSetCandidatesData["query"]>;
export function ChangeSetsPage({ accessToken }: { accessToken: string }) {
  useUiLanguage();
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
  useUiLanguage();
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const { productId, accessToken } = useChangeSetWorkspace();
  const location = useLocation();
  const history =
    params.get("tab") === "history" || location.pathname.endsWith("/history");
  return (
    <BranchWorkflowPanel key={`${productId}:${accessToken}`}>
      <div className="grid min-w-0 gap-(--space-lg)">
        <nav
          aria-label={t("Change set views")}
          className="flex flex-wrap gap-(--space-sm)"
        >
          <Button
            variant={history ? "outline" : "default"}
            aria-current={!history ? "page" : undefined}
            onClick={() =>
              navigate(`/products/${encodeURIComponent(productId)}/change-sets`)
            }
          >
            {t("Pending changes")}
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
            {t("Submission history")}
          </Button>
        </nav>
        {history ? <ChangeSetHistory /> : <CandidateList />}
      </div>
    </BranchWorkflowPanel>
  );
}
function CandidateList() {
  useUiLanguage();
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
        <AlertTitle>{t("Change set unavailable")}</AlertTitle>
        <AlertDescription>
          {t("This product's changes are unavailable to your account.")}
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
          {t("Change sets")}
        </h2>
        <p className="text-muted-foreground">
          {t("Select approved changes to prepare a pull request.")}
        </p>
      </div>
      {entryError && (
        <Alert>
          <AlertTitle>{t("Selected changes need review")}</AlertTitle>
          <AlertDescription>
            {t(
              "The saved proposal changed or is no longer eligible. Review the current version before selecting it.",
            )}
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
          {t("Search changes")}
          <Input
            id="change-query"
            value={query}
            maxLength={256}
            onChange={(event) => setQuery(event.target.value)}
          />
        </label>
        <label htmlFor="change-language">
          {t("Language")}
          <Input
            id="change-language"
            value={language}
            maxLength={64}
            onChange={(event) => setLanguage(event.target.value)}
            placeholder={t("All languages")}
          />
        </label>
        <div>
          <label id="proposal-state-label" htmlFor="proposal-state">
            {t("Proposal state")}
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
              <SelectItem value="approved">{t("Approved")}</SelectItem>
              <SelectItem value="all">{t("All pending")}</SelectItem>
              <SelectItem value="draft">{t("Draft")}</SelectItem>
              <SelectItem value="rejected">{t("Rejected")}</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <Button type="submit" variant="outline" className="w-fit">
          {t("Apply filters")}
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
          {t("Clear filters")}
        </Button>
      </form>
      <p className="text-sm text-muted-foreground">
        {t("Showing ")}
        {filters.state === "all"
          ? t("all pending")
          : statusLabel(filters.state)}{" "}
        {t("changes")}
        {filters.query ? t(" matching “{{v0}}”", { v0: filters.query }) : ""}
        {filters.language ? t(" in {{v0}}", { v0: filters.language }) : ""}.
      </p>
      {failure === filterKey && (
        <Alert variant="destructive">
          <AlertTitle>{t("Pending changes could not be loaded")}</AlertTitle>
          <AlertDescription>
            <Button
              variant="outline"
              onClick={() => setReload((value) => value + 1)}
            >
              {t("Retry loading changes")}
            </Button>
          </AlertDescription>
        </Alert>
      )}
      {!current && failure !== filterKey && (
        <p role="status">{t("Loading approved changes…")}</p>
      )}
      {current && !canRequest && (
        <Alert>
          <AlertTitle>{t("Submission access is read-only")}</AlertTitle>
          <AlertDescription>
            {t(
              "An admin or reviewer can submit approved changes. You can inspect changes and submission history.",
            )}
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
              ? t("No changes match these filters")
              : t("No approved changes ready")}
          </h3>
          <p>
            {filters.query ||
            filters.language ||
            filters.state !== "approved" ||
            filters.translation_group_id
              ? t("Clear filters to see the product's pending changes.")
              : t(
                  "Approve complete pending changes before creating a pull request. You can view other proposal states or return to Strings.",
                )}
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
            aria-label={t("Select loaded eligible changes")}
            checked={allLoaded ? true : someLoaded ? "indeterminate" : false}
            disabled={!eligible.length}
            onCheckedChange={(checked) => {
              if (checked) select(eligible);
              else for (const item of eligible) remove(item.proposal_id);
            }}
          />
          {t("Select loaded eligible changes")}
        </label>
      )}
      <ul className="grid gap-(--space-md)" aria-label={t("Pending changes")}>
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
                  aria-label={t("Select {{v0}} ({{v1}})", {
                    v0: item.key,
                    v1: item.language,
                  })}
                  onCheckedChange={(checked) =>
                    checked ? select([item]) : remove(item.proposal_id)
                  }
                />
              )}
              <span className="min-w-0 flex-1 wrap-anywhere">
                {item.key} ({item.language})
              </span>
              <Badge variant="outline">{statusLabel(item.state)}</Badge>
            </label>
            <p className="text-sm text-muted-foreground">
              {t("Version ")}
              {item.version} · {item.value_count} {t(" values")}
            </p>
            <p
              className="wrap-anywhere whitespace-pre-wrap"
              lang={item.language}
              dir="auto"
            >
              <span className="font-semibold">{t("Published: ")}</span>
              {item.published_excerpt}
            </p>
            <p
              className="wrap-anywhere whitespace-pre-wrap"
              lang={item.language}
              dir="auto"
            >
              <span className="font-semibold">{t("Proposed: ")}</span>
              {item.proposed_excerpt}
            </p>
            {item.blocker && (
              <p className="mt-(--space-sm) text-sm">
                {t("Selected changes need review:")}{" "}
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
          {t("Load more changes")}
        </Button>
      )}
      {selection.length > 0 && (
        <section
          aria-label={t("Selected changes")}
          className="grid gap-(--space-sm)"
        >
          <h3 className="font-semibold">
            {selection.length} {t(" selected · ")}
            {outside} {t(" outside current filters")}
          </h3>
          {selection.map((entry) => (
            <div
              key={entry.candidate.proposal_id}
              className="flex flex-wrap items-center gap-(--space-sm)"
            >
              <span className="min-w-0 wrap-anywhere">
                {entry.candidate.key} ({entry.candidate.language}
                {t("), version")} {entry.candidate.version}
                {entry.needsReview
                  ? t(" — Needs review: remove and select the current version.")
                  : ""}
              </span>
              <Button
                variant="ghost"
                onClick={() => remove(entry.candidate.proposal_id)}
                aria-label={t("Remove {{v0}} ({{v1}})", {
                  v0: entry.candidate.key,
                  v1: entry.candidate.language,
                })}
              >
                {t("Remove")}
              </Button>
            </div>
          ))}
        </section>
      )}
      {canRequest && (
        <>
          <p className="text-sm text-muted-foreground">
            {t("Select at most ")}
            {limit} {t(" complete proposals.")}
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
            {t("Review selected changes (")}
            {selection.length})
          </Button>
        </>
      )}
      {error && (
        <Alert variant="destructive">
          <AlertTitle>{t("Selected changes need review")}</AlertTitle>
          <AlertDescription>{t(error)}</AlertDescription>
        </Alert>
      )}
    </section>
  );
}
