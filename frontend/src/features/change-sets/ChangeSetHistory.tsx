import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { listChangeSets, type ChangeSetResponse } from "../../api/client";
import { Button } from "../../components/ui/button";
import { Alert, AlertTitle, AlertDescription } from "../../components/ui/alert";
import { useChangeSetWorkspace } from "./changeSetContext";
import { submissionStatus } from "./submissionStatus";
import { PullRequestLink } from "./SubmissionPresentation";

export function ChangeSetHistory() {
  const {
    accessToken,
    productId,
    returnFocus,
    setReturnFocus,
    historyMemory,
    setHistoryMemory,
    revokeRead,
  } = useChangeSetWorkspace();
  const [items, setItems] = useState<ChangeSetResponse[]>(
    historyMemory?.items ?? [],
  );
  const [cursor, setCursor] = useState<string | undefined>(
    historyMemory?.cursor,
  );
  const [next, setNext] = useState<string | null | undefined>(
    historyMemory?.next,
  );
  const [error, setError] = useState(false);
  const [unavailable, setUnavailable] = useState(false);
  const [reload, setReload] = useState(0);
  const [loading, setLoading] = useState(true);
  const heading = useRef<HTMLHeadingElement>(null);
  const focused = useRef(false);
  useEffect(() => {
    const controller = new AbortController();
    void listChangeSets({
      auth: accessToken,
      path: { product_id: productId },
      query: { cursor },
      signal: controller.signal,
    })
      .then((result) => {
        if (controller.signal.aborted) return;
        if ([401, 403, 404].includes(result.response?.status ?? 0)) {
          setUnavailable(true);
          setItems([]);
          setHistoryMemory(undefined);
          revokeRead();
          return;
        }
        if (!result.data) throw new Error("Unavailable");
        const page = result.data;
        setItems((old) =>
          cursor
            ? [
                ...old.filter(
                  (item) => !page.items.some((next) => next.id === item.id),
                ),
                ...page.items,
              ]
            : page.items,
        );
        setNext(page.next_cursor);
        setError(false);
      })
      .catch(() => {
        if (!controller.signal.aborted) setError(true);
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [accessToken, productId, cursor, reload, setHistoryMemory, revokeRead]);
  useEffect(() => {
    if (next !== undefined && !unavailable)
      setHistoryMemory({ items, cursor, next });
  }, [items, cursor, next, unavailable, setHistoryMemory]);
  useEffect(() => {
    if (loading || focused.current) return;
    focused.current = true;
    (returnFocus ? document.getElementById(returnFocus) : null)?.focus({
      preventScroll: true,
    });
    if (!returnFocus || !document.getElementById(returnFocus))
      heading.current?.focus({ preventScroll: true });
    setReturnFocus(undefined);
  }, [loading, returnFocus, setReturnFocus]);
  return (
    <section
      className="grid min-w-0 gap-(--space-lg)"
      aria-labelledby="submission-history-heading"
    >
      <h2
        ref={heading}
        tabIndex={-1}
        id="submission-history-heading"
        className="text-heading font-semibold"
      >
        Submission history
      </h2>
      {unavailable ? (
        <Alert>
          <AlertTitle>Change set unavailable</AlertTitle>
          <AlertDescription>
            This history is unavailable to your account.
          </AlertDescription>
        </Alert>
      ) : (
        <>
          {loading && <p role="status">Loading submission history…</p>}
          {error && (
            <Alert>
              <AlertTitle>Submission history could not be loaded</AlertTitle>
              <AlertDescription>
                <Button
                  variant="outline"
                  onClick={() => {
                    setLoading(true);
                    setReload((n) => n + 1);
                  }}
                >
                  Retry loading history
                </Button>
              </AlertDescription>
            </Alert>
          )}
          {!loading && !error && !items.length && (
            <div>
              <h3 className="font-semibold">No submissions yet</h3>
            </div>
          )}
          <ul className="grid min-w-0 gap-(--space-lg)">
            {items.map((item) => (
              <li
                key={item.id}
                className="min-w-0 space-y-(--space-sm) rounded-lg border p-(--space-lg)"
              >
                <h3 className="font-semibold wrap-anywhere">
                  {item.workspace}/{item.repository_slug} → {item.target_branch}
                </h3>
                <p>
                  {submissionStatus(item)} · {item.proposal_count} proposals ·{" "}
                  {item.value_count} values · {item.file_count} files
                </p>
                <p className="wrap-anywhere">
                  Submitted by {item.actor?.display_name ?? "Unknown user"}
                </p>
                <p>
                  Accepted{" "}
                  <time dateTime={item.created_at}>
                    {new Date(item.created_at).toLocaleString()}
                  </time>
                </p>
                <div className="flex flex-wrap gap-(--space-md)">
                  <Link
                    id={`history-${item.id}`}
                    className="inline-flex min-h-[44px] items-center underline"
                    to={`/products/${encodeURIComponent(productId)}/change-sets/${encodeURIComponent(item.id)}`}
                    onClick={() => setReturnFocus(`history-${item.id}`)}
                  >
                    View change set
                    <span className="sr-only">
                      {" "}
                      for {item.repository_slug}, {item.target_branch}
                    </span>
                  </Link>
                  <PullRequestLink record={item} />
                </div>
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
              Load more submissions
            </Button>
          )}
        </>
      )}
    </section>
  );
}
