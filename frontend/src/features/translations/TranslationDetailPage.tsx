import { useEffect, useRef, useState, type ReactNode } from "react";
import { Link, useOutletContext, useParams } from "react-router-dom";
import {
  getTranslationGroup,
  type TranslationGroupDetailResponse,
  type TranslationProvenanceResponse,
  type TranslationValueResponse,
} from "../../api/client";
import { Alert, AlertDescription, AlertTitle } from "../../components/ui/alert";
import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { Skeleton } from "../../components/ui/skeleton";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "../../components/ui/tooltip";
import type { TranslationsWorkspaceContext } from "./TranslationsWorkspace";
import {
  MaximumLengthDialog,
  type ConstraintMutationMode,
} from "./MaximumLengthDialog";
import {
  completeTranslationDetail,
  lengthStatusLabel,
  reviewStateLabel,
  ruleSourceLabel,
} from "./translationDetailAuthority";

const sectionClass =
  "min-w-0 space-y-(--space-md) rounded-lg border bg-secondary p-(--space-lg)";
const actionClass = "min-h-[44px] h-auto whitespace-normal";
const selectorNames: Record<string, string> = {
  quantity: "Quantity",
  index: "Array position",
  position: "Array position",
  form: "Numerus form",
  variant: "Length variant",
  segments: "JSON path segments",
  path: "JSON path segments",
};
const kindNames = {
  scalar: "Default value",
  android_quantity: "Plural",
  android_array_item: "Array",
  qt_numerus: "Qt numerus",
  qt_length_variant: "Qt length variant",
  json_path: "JSON path",
};

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section aria-label={title} className={sectionClass}>
      <h2 className="text-heading font-semibold">{title}</h2>
      {children}
    </section>
  );
}

function Commit({ hash }: { hash: string }) {
  const [notice, setNotice] = useState("");
  const live = useRef(true);
  useEffect(() => {
    live.current = true;
    return () => {
      live.current = false;
    };
  }, []);
  return (
    <div className="flex min-w-0 flex-wrap items-center gap-(--space-sm)">
      <code className="wrap-anywhere">{hash.slice(0, 12)}</code>
      <TooltipProvider>
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              variant="outline"
              className={actionClass}
              onClick={() => {
                void navigator.clipboard.writeText(hash).then(
                  () => {
                    if (live.current) setNotice("Full commit copied");
                  },
                  () => {
                    if (live.current) setNotice("Commit could not be copied");
                  },
                );
              }}
            >
              Copy full commit
            </Button>
          </TooltipTrigger>
          <TooltipContent>Copy full commit</TooltipContent>
        </Tooltip>
      </TooltipProvider>
      {notice && <span role="status">{notice}</span>}
    </div>
  );
}

function TranslationProvenance({
  value,
}: {
  value: TranslationProvenanceResponse | null;
}) {
  if (!value) return <p>Source location unavailable</p>;
  return (
    <dl className="grid min-w-0 gap-(--space-sm)">
      {[
        ["Repository", value.repository_name],
        ["Branch", value.branch],
        ["File path", value.path],
        ["Format", value.format],
        ["Repository side", value.repository_side],
        ["Line", value.line ?? "Line unavailable"],
        ["Column", value.column ?? "Column unavailable"],
        ["Execution", value.execution_id],
      ].map(([label, text]) => (
        <div key={label} className="min-w-0">
          <dt className="text-label font-semibold">{label}</dt>
          <dd className="font-mono wrap-anywhere">{text}</dd>
        </div>
      ))}
      <div>
        <dt className="text-label font-semibold">Import commit</dt>
        <dd>
          <Commit hash={value.commit_hash} />
        </dd>
      </div>
    </dl>
  );
}

function TranslationHistory({ value }: { value: TranslationValueResponse }) {
  return (
    <div className="space-y-(--space-sm)">
      <h4 className="font-semibold">History</h4>
      {!value.history?.length ? (
        <p>No revision history available</p>
      ) : (
        <ol className="space-y-(--space-md)">
          {value.history.map((entry) => (
            <li
              key={entry.revision_number}
              className="min-w-0 space-y-(--space-sm)"
            >
              <p>Revision {entry.revision_number}</p>
              <p>
                {reviewStateLabel(entry.review_state)}
                {entry.is_deleted ? " · Deleted in source" : ""}
              </p>
              <time dateTime={entry.created_at}>{entry.created_at}</time>
              <p className="font-mono wrap-anywhere">{entry.execution_id}</p>
              <Commit hash={entry.commit_hash} />
            </li>
          ))}
        </ol>
      )}
      {value.history_has_more && (
        <p>
          Showing the latest 50 revisions. Earlier history is retained on the
          server.
        </p>
      )}
    </div>
  );
}

function TranslationValueCard({
  value,
  detail,
}: {
  value: TranslationValueResponse;
  detail: TranslationGroupDetailResponse;
}) {
  return (
    <article
      id={`value-${value.id}`}
      aria-label={`${kindNames[value.selector_kind]} ${value.id}`}
      className="min-w-0 space-y-(--space-md) border-b pb-(--space-lg) last:border-0"
    >
      <h3 className="text-heading font-semibold">
        {kindNames[value.selector_kind]}
      </h3>
      <dl className="grid min-w-0 gap-(--space-sm)">
        <div>
          <dt className="text-label font-semibold">Value ID</dt>
          <dd className="font-mono wrap-anywhere">{value.id}</dd>
        </div>
        {value.selector_fields?.map((field) => (
          <div key={field.name}>
            <dt className="text-label font-semibold">
              {selectorNames[field.name] ?? field.name}
            </dt>
            <dd className="font-mono wrap-anywhere">
              {Array.isArray(field.value)
                ? JSON.stringify(field.value)
                : String(field.value)}
            </dd>
          </div>
        ))}
        {value.selector_fields === null && (
          <div>
            <dt>Selector</dt>
            <dd>Selector metadata unavailable</dd>
          </div>
        )}
      </dl>
      <p>{reviewStateLabel(value.review_state)}</p>
      {value.is_deleted && (
        <>
          <Badge variant="outline">Deleted in source</Badge>
          <p className="wrap-anywhere">
            Deleted at: {value.deleted_at ?? "Date unavailable"}
          </p>
        </>
      )}
      <div>
        <h4 className="font-semibold">Source text</h4>
        <p
          className="whitespace-pre-wrap wrap-anywhere"
          lang={detail.base_language ?? undefined}
          dir="auto"
        >
          {value.source_text === null
            ? "No source text available"
            : value.source_text || "Empty source text"}
        </p>
      </div>
      <div>
        <h4 className="font-semibold">Translated text</h4>
        <p
          data-testid={`target-${value.id}`}
          className="whitespace-pre-wrap wrap-anywhere"
          lang={detail.language}
          dir="auto"
        >
          {value.translated_text || "Empty translation"}
        </p>
      </div>
      {value.structure.length > 0 && (
        <details>
          <summary className="min-h-[44px] cursor-pointer">
            Format structure
          </summary>
          <pre className="whitespace-pre-wrap wrap-anywhere text-body">
            {JSON.stringify(value.structure, null, 2)}
          </pre>
        </details>
      )}
      <p>
        Actual: {value.constraint.actual} characters · Maximum:{" "}
        {value.constraint.maximum ?? "None"}
      </p>
      <p>{lengthStatusLabel(value.constraint)}</p>
      <TranslationHistory value={value} />
    </article>
  );
}

function LoadedDetail({
  detail,
  onChanged,
}: {
  detail: TranslationGroupDetailResponse;
  onChanged: (detail: TranslationGroupDetailResponse) => void;
}) {
  const context = useOutletContext<TranslationsWorkspaceContext>();
  const [dialog, setDialog] = useState<{
    mode: ConstraintMutationMode;
    trigger: HTMLButtonElement;
    fallback: HTMLButtonElement | null;
  } | null>(null);
  const primaryAction = useRef<HTMLButtonElement>(null);
  const canMutate =
    context.principal.roles.some(
      (role) => role === "admin" || role === "product_manager_reviewer",
    ) &&
    detail.base_language !== null &&
    !detail.is_deleted &&
    detail.values.every((value) => value.selector_fields !== null);
  const mutationLabel =
    detail.explicit_maximum !== null
      ? "Edit max length"
      : detail.language !== detail.base_language && detail.base_maximum !== null
        ? "Add language override"
        : "Set max length";
  const over = detail.values.filter(
    (v) => v.constraint.status === "over_limit",
  ).length;
  const partial = detail.values.some(
    (v) =>
      !v.provenance ||
      v.provenance.line === null ||
      v.source_text === null ||
      !v.history?.length ||
      v.selector_fields === null,
  );
  return (
    <>
      <header className="space-y-(--space-sm)">
        <p className="font-mono wrap-anywhere">{detail.raw_key}</p>
        <p>
          {detail.language_label} ({detail.language})
        </p>
        {detail.is_deleted && (
          <Badge variant="outline">Deleted in source</Badge>
        )}
      </header>
      {partial && (
        <Alert>
          <AlertTitle>
            Some source or history metadata is unavailable
          </AlertTitle>
          <AlertDescription>
            The available translation content remains readable.
          </AlertDescription>
        </Alert>
      )}
      {over > 0 && (
        <Alert className="border-warning bg-warning/10 text-warning">
          <AlertTitle>
            {over} of {detail.values.length} over limit
          </AlertTitle>
          <AlertDescription>
            This translation can remain Draft, but it cannot be approved or
            submitted while over the limit.
          </AlertDescription>
        </Alert>
      )}
      <div className="grid min-w-0 gap-(--space-xl) xl:grid-cols-[minmax(0,2fr)_minmax(18rem,1fr)]">
        <Section title="Translation content">
          <p>{reviewStateLabel(detail.state_summary)}</p>
          {detail.values.map((value) => (
            <TranslationValueCard
              key={value.id}
              value={value}
              detail={detail}
            />
          ))}
        </Section>
        <aside className="min-w-0 space-y-(--space-xl)">
          <Section title="Maximum length">
            {canMutate && (
              <div className="flex flex-wrap gap-(--space-sm)">
                <Button
                  ref={primaryAction}
                  className={actionClass}
                  onClick={(event) =>
                    setDialog({
                      mode:
                        detail.explicit_maximum === null ? "create" : "edit",
                      trigger: event.currentTarget,
                      fallback: primaryAction.current,
                    })
                  }
                >
                  {mutationLabel}
                </Button>
                {detail.explicit_maximum !== null && (
                  <Button
                    className={actionClass}
                    variant="outline"
                    onClick={(event) =>
                      setDialog({
                        mode: "remove",
                        trigger: event.currentTarget,
                        fallback: primaryAction.current,
                      })
                    }
                  >
                    {detail.language === detail.base_language
                      ? "Remove base limit"
                      : "Remove language override"}
                  </Button>
                )}
              </div>
            )}
            <p>{ruleSourceLabel(detail)}</p>
            {detail.values.map((value) => (
              <div key={value.id} className="space-y-(--space-sm)">
                <p className="font-mono wrap-anywhere">{value.id}</p>
                <p>
                  Actual: {value.constraint.actual} · Maximum:{" "}
                  {value.constraint.maximum ?? "None"}
                </p>
                <p>{lengthStatusLabel(value.constraint)}</p>
              </div>
            ))}
          </Section>
          <Section title="Source context">
            <p className="wrap-anywhere">Product: {detail.product_name}</p>
            {detail.values.map((value) => (
              <div key={value.id} className="min-w-0 space-y-(--space-sm)">
                <p className="font-mono wrap-anywhere">{value.id}</p>
                <TranslationProvenance value={value.provenance} />
              </div>
            ))}
          </Section>
          <Section title="Review context">
            <p>{reviewStateLabel(detail.state_summary)}</p>
            <p>Pending change: None</p>
            <p>Comments: No comments yet</p>
          </Section>
        </aside>
      </div>
      {dialog && (
        <MaximumLengthDialog
          accessToken={context.accessToken}
          detail={detail}
          roles={context.principal.roles}
          mode={dialog.mode}
          triggerElement={dialog.trigger}
          fallbackElement={dialog.fallback}
          onClose={() => setDialog(null)}
          onChanged={(fresh) => {
            if (context.snapshot)
              context.setSnapshot({
                ...context.snapshot,
                pages: [],
                invalidated: true,
              });
            onChanged(fresh);
          }}
        />
      )}
    </>
  );
}

function DetailRequest({
  id,
  accessToken,
}: {
  id: string;
  accessToken: string;
}) {
  const [attempt, setAttempt] = useState(0);
  const [load, setLoad] = useState<{
    attempt: number;
    data?: TranslationGroupDetailResponse;
    error?: "missing" | "general";
  }>({ attempt: 0 });
  const current = load.attempt === attempt ? load : null;
  const heading = useRef<HTMLHeadingElement>(null);
  const errorAlert = useRef<HTMLDivElement>(null);
  const hasData = Boolean(current?.data);
  const currentError = current?.error;
  useEffect(() => {
    if (hasData) heading.current?.focus({ preventScroll: true });
  }, [hasData]);
  useEffect(() => {
    if (attempt === 0 || !currentError) return;
    let active = true;
    queueMicrotask(() => {
      if (active) errorAlert.current?.focus();
    });
    return () => {
      active = false;
    };
  }, [attempt, currentError]);
  useEffect(() => {
    const controller = new AbortController();
    void (async () => {
      try {
        const result = await getTranslationGroup({
          auth: accessToken,
          path: { translation_group_id: id },
          signal: controller.signal,
        });
        if (controller.signal.aborted) return;
        if (!result.data) {
          setLoad({
            attempt,
            error: [403, 404].includes(result.response?.status ?? 0)
              ? "missing"
              : "general",
          });
          return;
        }
        if (!completeTranslationDetail(result.data, id))
          throw new Error("Invalid detail projection");
        setLoad({ attempt, data: result.data });
      } catch {
        if (!controller.signal.aborted) setLoad({ attempt, error: "general" });
      }
    })();
    return () => controller.abort();
  }, [accessToken, id, attempt]);
  return (
    <div className="grid min-w-0 gap-(--space-xl)">
      <Link
        to="/translations"
        className="inline-flex min-h-[44px] items-center underline"
      >
        Back to translations
      </Link>
      <h1 ref={heading} tabIndex={-1} className="text-display font-semibold">
        Translation details
      </h1>
      {current?.data ? (
        <LoadedDetail
          detail={current.data}
          onChanged={(data) => setLoad({ attempt, data })}
        />
      ) : current?.error ? (
        <Alert ref={errorAlert} tabIndex={-1}>
          <AlertTitle>
            {current.error === "missing"
              ? "Translation not available"
              : "Translation details unavailable"}
          </AlertTitle>
          <AlertDescription>
            {current.error === "missing" ? (
              "This translation may have been removed or is outside your authorized products."
            ) : (
              <>
                <p>
                  We could not load this translation. Retry without losing your
                  search.
                </p>
                <Button
                  className={actionClass}
                  variant="outline"
                  onClick={() => setAttempt((n) => n + 1)}
                >
                  Retry details
                </Button>
              </>
            )}
          </AlertDescription>
        </Alert>
      ) : (
        <div role="status">
          <p>Loading translation details</p>
          <Skeleton className="h-12 w-full" />
          <div className="mt-(--space-xl) grid gap-(--space-xl) xl:grid-cols-2">
            <Skeleton className="h-96 w-full" />
            <Skeleton className="h-96 w-full" />
          </div>
        </div>
      )}
    </div>
  );
}

export function TranslationDetailPage() {
  const { translationGroupId = "" } = useParams<"translationGroupId">();
  const { accessToken, principal } =
    useOutletContext<TranslationsWorkspaceContext>();
  return (
    <DetailRequest
      key={`${principal.id}:${accessToken}:${translationGroupId}`}
      id={translationGroupId}
      accessToken={accessToken}
    />
  );
}
