import { useEffect, useState } from "react";
import {
  listCodeKeys,
  listProductCodeSources,
  type CodeCatalogEntry,
  type CodeSourceSummary,
} from "../../api/client";
import { Button } from "../../components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "../../components/ui/dialog";

function Catalog({
  accessToken,
  productId,
}: {
  accessToken: string;
  productId: string;
}) {
  const [sources, setSources] = useState<CodeSourceSummary[] | null>(null);
  const [sourceCursor, setSourceCursor] = useState<string | null>(null);
  const [scope, setScope] = useState("");
  const [items, setItems] = useState<CodeCatalogEntry[]>([]);
  const [cursor, setCursor] = useState<string | null>(null);
  const [orphanCount, setOrphanCount] = useState(0);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    void listProductCodeSources({
      auth: accessToken,
      path: { product_id: productId },
      signal: controller.signal,
    })
      .then((result) => {
        if (controller.signal.aborted) return;
        if (!result.data) throw new Error("Code sources unavailable");
        setSources(result.data.items);
        setSourceCursor(result.data.next_cursor);
        setScope(result.data.items[0]?.scope_id ?? "");
      })
      .catch(() => {
        if (!controller.signal.aborted)
          setError("Could not load code sources. Close and reopen to retry.");
      });
    return () => controller.abort();
  }, [accessToken, productId]);
  useEffect(() => {
    if (!scope) return;
    const controller = new AbortController();
    void listCodeKeys({
      auth: accessToken,
      path: { scope_id: scope },
      signal: controller.signal,
    })
      .then((result) => {
        if (controller.signal.aborted) return;
        if (!result.data) throw new Error("Code catalog unavailable");
        setItems(result.data.items);
        setCursor(result.data.next_cursor);
        setOrphanCount(result.data.orphan_count);
      })
      .catch(() => {
        if (!controller.signal.aborted)
          setError("Could not load the code catalog.");
      });
    return () => controller.abort();
  }, [accessToken, scope]);
  async function more() {
    if (!scope || !cursor || loading) return;
    setLoading(true);
    try {
      const result = await listCodeKeys({
        auth: accessToken,
        path: { scope_id: scope },
        query: { after: cursor },
      });
      if (!result.data) throw new Error("Code catalog unavailable");
      setItems((current) => [...current, ...result.data.items]);
      setCursor(result.data.next_cursor);
    } catch {
      setError("Could not load more keys.");
    } finally {
      setLoading(false);
    }
  }
  async function moreSources() {
    if (!sourceCursor || loading) return;
    setLoading(true);
    try {
      const result = await listProductCodeSources({
        auth: accessToken,
        path: { product_id: productId },
        query: { after: sourceCursor },
      });
      if (!result.data) throw new Error("Code sources unavailable");
      setSources((current) => [...(current ?? []), ...result.data.items]);
      setSourceCursor(result.data.next_cursor);
    } catch {
      setError("Could not load more sources.");
    } finally {
      setLoading(false);
    }
  }
  return (
    <div className="space-y-4">
      {error && <p role="alert">{error}</p>}
      {sources === null && !error && <p role="status">Loading code sources…</p>}
      {sources?.length === 0 && (
        <p>No Kotlin or Java catalog has been imported for this product.</p>
      )}
      {sources && sources.length > 0 && (
        <>
          <label className="grid gap-2 text-sm">
            Code source
            <select
              className="rounded-md border bg-background p-2"
              value={scope}
              disabled={loading}
              onChange={(e) => {
                setScope(e.target.value);
                setItems([]);
                setCursor(null);
              }}
            >
              {sources.map((source, i) => (
                <option key={source.scope_id} value={source.scope_id}>
                  Source {i + 1} · {source.key_count} keys ·{" "}
                  {source.missing_count} without translations
                </option>
              ))}
            </select>
          </label>
          {sourceCursor && (
            <Button
              variant="outline"
              disabled={loading}
              onClick={() => void moreSources()}
            >
              More sources
            </Button>
          )}
          <p className="text-sm text-muted-foreground">
            Use Add text to propose a translation for an existing code key. New
            key identifiers must be added in the application repository.
          </p>
          <p className="text-sm">
            {orphanCount} translation keys are outside this code catalog.
          </p>
          <ul className="max-h-80 space-y-2 overflow-auto">
            {items.map((item) => (
              <li key={item.key} className="rounded border p-2 text-sm">
                <code className="wrap-anywhere">{item.key}</code>
                {item.missing_translation && <p>No imported translation</p>}
                {!item.missing_translation && item.missing_base && (
                  <p>Base text missing</p>
                )}
              </li>
            ))}
          </ul>
          {cursor && (
            <Button
              variant="outline"
              disabled={loading}
              onClick={() => void more()}
            >
              {loading ? "Loading…" : "More keys"}
            </Button>
          )}
        </>
      )}
    </div>
  );
}

export function CodeKeyCatalog(props: {
  accessToken: string;
  productId: string;
}) {
  const [open, setOpen] = useState(false);
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="outline">Code keys</Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Application code keys</DialogTitle>
          <DialogDescription>
            The complete imported catalog includes keys that have no translation
            yet.
          </DialogDescription>
        </DialogHeader>
        {open && <Catalog key={props.productId} {...props} />}
      </DialogContent>
    </Dialog>
  );
}
