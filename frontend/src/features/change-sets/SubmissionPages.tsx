import { useEffect, useRef, useState, type ReactNode } from "react";
import {
  getChangeSetItems,
  getChangeSetValues,
  getChangeSetFiles,
  getChangeSetActivity,
  type ChangeSetItemResponse,
  type ChangeSetFileResponse,
  type ChangeSetValueResponse,
  type ChangeSetActivityResponse,
  type ChangeSetItemsPage,
} from "../../api/client";
import { Button } from "../../components/ui/button";
import { useChangeSetWorkspace } from "./changeSetContext";

type Page<T> = Omit<ChangeSetItemsPage, "items"> & { items: T[] };
type Loader<T> = (options: {
  auth: string;
  path: { product_id: string; change_set_id: string };
  query: { cursor?: string };
  signal: AbortSignal;
}) => Promise<{ data?: Page<T>; response?: Response }>;
function PagedSection<T>({
  id,
  heading,
  more,
  load,
  render,
  onUnavailable,
}: {
  id: string;
  heading: string;
  more: string;
  load: Loader<T>;
  render: (item: T) => ReactNode;
  onUnavailable: () => void;
}) {
  const { accessToken, productId } = useChangeSetWorkspace();
  const [items, setItems] = useState<T[]>([]);
  const [cursor, setCursor] = useState<string>();
  const [next, setNext] = useState<string | null>();
  const [error, setError] = useState(false);
  const [loading, setLoading] = useState(true);
  const [retry, setRetry] = useState(0);
  const summary = useRef<HTMLParagraphElement>(null);
  useEffect(() => {
    const controller = new AbortController();
    void load({
      auth: accessToken,
      path: { product_id: productId, change_set_id: id },
      query: { cursor },
      signal: controller.signal,
    })
      .then((result) => {
        if (controller.signal.aborted) return;
        if ([401, 403, 404].includes(result.response?.status ?? 0)) {
          setItems([]);
          onUnavailable();
          return;
        }
        if (!result.data) throw new Error("Unavailable");
        const page = result.data;
        setItems((old) => (cursor ? [...old, ...page.items] : page.items));
        setNext(page.next_cursor);
        setError(false);
      })
      .catch(() => {
        if (!controller.signal.aborted) {
          setError(true);
          if (cursor || retry) queueMicrotask(() => summary.current?.focus());
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [accessToken, productId, id, cursor, retry, load, onUnavailable]);
  return (
    <section className="grid min-w-0 gap-(--space-md)" aria-label={heading}>
      <h3 className="text-heading font-semibold">{heading}</h3>
      {loading && <p role="status">Loading {heading.toLowerCase()}…</p>}
      {error && (
        <p ref={summary} tabIndex={-1} role="alert">
          {heading} could not be loaded.{" "}
          <Button
            variant="outline"
            onClick={() => {
              setLoading(true);
              setRetry((n) => n + 1);
            }}
          >
            Retry {heading.toLowerCase()}
          </Button>
        </p>
      )}
      {!loading && !error && !items.length && (
        <p>No {heading.toLowerCase()} recorded.</p>
      )}
      <ul className="grid min-w-0 gap-(--space-md)">
        {items.map((item, index) => (
          <li
            key={index}
            className="min-w-0 space-y-(--space-sm) border-b pb-(--space-md) wrap-anywhere"
          >
            {render(item)}
          </li>
        ))}
      </ul>
      {next && (
        <Button
          className="w-fit"
          variant="outline"
          disabled={loading}
          onClick={() => {
            setLoading(true);
            setCursor(next);
          }}
        >
          {more}
        </Button>
      )}
    </section>
  );
}

export function SubmissionPages({
  id,
  onUnavailable,
}: {
  id: string;
  onUnavailable: () => void;
}) {
  return (
    <>
      <PagedSection<ChangeSetItemResponse>
        id={id}
        onUnavailable={onUnavailable}
        heading="Included proposals"
        more="Load more proposals"
        load={getChangeSetItems}
        render={(item) => (
          <>
            <p>
              {item.key} ({item.language}) · Submitted version{" "}
              {item.proposal_version} · {item.value_count} values
            </p>
            {item.newer_version_available && (
              <p className="font-semibold">
                Newer proposal available · Current version{" "}
                {item.current_version}. The submitted version remains unchanged.
              </p>
            )}
          </>
        )}
      />
      <PagedSection<ChangeSetFileResponse>
        id={id}
        onUnavailable={onUnavailable}
        heading="File changes"
        more="Load more files"
        load={getChangeSetFiles}
        render={(item) => (
          <>
            <p className="font-mono">{item.path}</p>
            <p>
              {item.format ?? "Format unavailable"} · {item.changed_values}{" "}
              changed values
            </p>
            <p>
              Before: {item.before_sha256} ({item.before_bytes} bytes)
            </p>
            <p>
              After: {item.after_sha256} ({item.after_bytes} bytes)
            </p>
          </>
        )}
      />
      <PagedSection<ChangeSetValueResponse>
        id={id}
        onUnavailable={onUnavailable}
        heading="Submitted values"
        more="Load more diff entries"
        load={getChangeSetValues}
        render={(item) => (
          <>
            <p>
              {item.key} ({item.language}) · Version {item.proposal_version} ·{" "}
              {item.selector_kind}: {item.selector}
            </p>
            <p className="font-mono">{item.file_path}</p>
            <div className="grid min-w-0 gap-(--space-md) md:grid-cols-2">
              <div>
                <h4 className="font-semibold">Published at submission</h4>
                <p
                  lang={item.language}
                  dir="auto"
                  className="whitespace-pre-wrap wrap-anywhere"
                >
                  {item.published_text}
                </p>
              </div>
              <div>
                <h4 className="font-semibold">Submitted proposal</h4>
                <p
                  lang={item.language}
                  dir="auto"
                  className="whitespace-pre-wrap wrap-anywhere"
                >
                  {item.proposed_text}
                </p>
              </div>
            </div>
            <p>
              Imported revision {item.basis_revision_number} ·{" "}
              {item.basis_digest}
            </p>
          </>
        )}
      />
      <PagedSection<ChangeSetActivityResponse>
        id={id}
        onUnavailable={onUnavailable}
        heading="Activity"
        more="Load more activity"
        load={getChangeSetActivity}
        render={(item) => (
          <>
            <p>
              Attempt {item.attempt} · {item.step.replaceAll("_", " ")} ·{" "}
              {item.outcome.replaceAll("_", " ")}
            </p>
            <time dateTime={item.created_at}>
              {new Date(item.created_at).toLocaleString()}
            </time>
            {item.receipt?.kind === "branch" && (
              <p>
                Branch {item.receipt.name} · {item.receipt.commit_hash}
              </p>
            )}
            {item.receipt?.kind === "commit" && (
              <p>
                Commit {item.receipt.commit_hash} · Parent {item.receipt.parent}
              </p>
            )}
            {item.receipt?.kind === "pull_request" && (
              <p>
                Pull request #{item.receipt.id} · {item.receipt.state} · Commit{" "}
                {item.receipt.source_commit}
              </p>
            )}
            {item.receipt?.kind === "authority" && (
              <p>{item.receipt.action.replaceAll("_", " ")}</p>
            )}
          </>
        )}
      />
    </>
  );
}
