import { useEffect, useId, useState } from "react";
import {
  getAdminImportDuplicates,
  getAdminPreviewDuplicates,
  type DuplicateReportResponse,
} from "../../../api/client";
import { Button } from "../../../components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "../../../components/ui/dialog";
import { Input } from "../../../components/ui/input";
import { Label } from "../../../components/ui/label";

export interface DuplicateKeysDialogProps {
  accessToken: string;
  previewJobId?: string;
  productId?: string;
  importId?: string;
  execution?: number;
}

export function DuplicateKeysDialog(props: DuplicateKeysDialogProps) {
  // Authority changes destroy open state, filters and every in-flight response.
  return (
    <DiagnosticView
      key={JSON.stringify([
        props.accessToken,
        props.previewJobId,
        props.productId,
        props.importId,
        props.execution,
      ])}
      {...props}
    />
  );
}

function DiagnosticView({
  accessToken,
  previewJobId,
  productId,
  importId,
  execution,
}: DuplicateKeysDialogProps) {
  const [open, setOpen] = useState(false);
  const [language, setLanguage] = useState("");
  const [file, setFile] = useState("");
  const [query, setQuery] = useState<{
    language?: string;
    file?: string;
    cursor?: string;
    group_id?: string;
  }>({});
  const [retry, setRetry] = useState(0);
  const [state, setState] = useState<{
    data?: DuplicateReportResponse;
    error?: string;
  }>({});
  const id = useId();
  useEffect(() => {
    if (!open) return;
    const controller = new AbortController();
    void (async () => {
      await Promise.resolve();
      if (controller.signal.aborted) return;
      setState({});
      try {
        const options = { auth: accessToken, signal: controller.signal, query };
        const result =
          previewJobId !== undefined
            ? await getAdminPreviewDuplicates({
                ...options,
                path: { job_id: previewJobId },
              })
            : await getAdminImportDuplicates({
                ...options,
                path: { product_id: productId!, import_id: importId! },
                query: { ...query, execution: execution! },
              });
        if (controller.signal.aborted) return;
        if (result.data === undefined) {
          setState({
            error:
              result.response?.status === 404
                ? "No stored report is available for this execution. Run a fresh validation or import."
                : "Could not load duplicate diagnostics.",
          });
        } else setState({ data: result.data });
      } catch {
        if (!controller.signal.aborted)
          setState({ error: "Could not load duplicate diagnostics." });
      }
    })();
    return () => controller.abort();
  }, [
    accessToken,
    execution,
    importId,
    open,
    previewJobId,
    productId,
    query,
    retry,
  ]);
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button type="button" variant="outline">
          View duplicate keys
        </Button>
      </DialogTrigger>
      <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-4xl">
        <DialogHeader>
          <DialogTitle>Duplicate keys</DialogTitle>
          <DialogDescription>
            Read-only diagnostics. Unique strings continue to import while
            duplicate identities stay quarantined. Correct them in Bitbucket,
            then import again. Existing valid translations are unchanged.
          </DialogDescription>
        </DialogHeader>
        <p>Only duplicate keys</p>
        <form
          className="flex flex-wrap items-end gap-3"
          onSubmit={(event) => {
            event.preventDefault();
            setState({});
            setQuery({
              language: language || undefined,
              file: file || undefined,
            });
          }}
        >
          <div>
            <Label htmlFor={`${id}-language`}>Language (exact)</Label>
            <Input
              id={`${id}-language`}
              maxLength={64}
              value={language}
              onChange={(event) => setLanguage(event.target.value)}
            />
          </div>
          <div>
            <Label htmlFor={`${id}-file`}>File (exact path)</Label>
            <Input
              id={`${id}-file`}
              maxLength={4096}
              value={file}
              onChange={(event) => setFile(event.target.value)}
            />
          </div>
          <Button type="submit" variant="outline">
            Apply filters
          </Button>
        </form>
        {state.error ? (
          <div role="alert">
            <p>{state.error}</p>
            <Button
              type="button"
              onClick={() => setRetry((value) => value + 1)}
            >
              Retry diagnostics
            </Button>
          </div>
        ) : !state.data ? (
          <p role="status">Loading duplicate diagnostics…</p>
        ) : (
          <>
            <p>
              {state.data.group_count} duplicate groups ·{" "}
              {state.data.repeated_occurrences} repeated occurrences
            </p>
            <p>
              Report execution {state.data.execution} · {state.data.report_id}
            </p>
            {!state.data.complete ? (
              <p role="alert">
                Incomplete diagnostic scan. These counts do not cover all source
                files. Publication and import remain blocked.{" "}
                {state.data.issue_codes.join(", ")}
              </p>
            ) : null}
            {state.data.sources.map((source) => (
              <p
                className="break-all text-sm"
                key={`${source.repository_side}:${source.commit_hash}`}
              >
                {source.repository_side}: {source.repository_id} ·{" "}
                {source.source_branch} · {source.commit_hash}
              </p>
            ))}
            <div className="space-y-4">
              {state.data.items.map((group) => (
                <section
                  className="rounded-md border p-3 [overflow-wrap:anywhere]"
                  key={group.id}
                >
                  <h3 className="font-semibold">{group.key_preview}</h3>
                  {group.key_length > group.key_preview.length ? (
                    <p>Abbreviated key · {group.key_length} characters</p>
                  ) : null}
                  <p>
                    {group.language} · {group.repository_side} ·{" "}
                    {group.occurrence_count} occurrences
                  </p>
                  <ul>
                    {group.occurrences.map((occurrence) => (
                      <li
                        key={`${occurrence.path}:${occurrence.resource_position}`}
                      >
                        {occurrence.path} · Resource position{" "}
                        {occurrence.resource_position} (zero-based)
                      </li>
                    ))}
                  </ul>
                  {group.next_occurrence_cursor ? (
                    <Button
                      type="button"
                      variant="outline"
                      onClick={() => {
                        setState({});
                        setQuery({
                          ...query,
                          group_id: group.id,
                          cursor: group.next_occurrence_cursor!,
                        });
                      }}
                    >
                      More occurrences
                    </Button>
                  ) : null}
                </section>
              ))}
            </div>
            {state.data.items.length === 0 ? (
              <p>No duplicate groups match these filters.</p>
            ) : null}
            {state.data.next_cursor ? (
              <Button
                type="button"
                variant="outline"
                onClick={() => {
                  const cursor = state.data!.next_cursor!;
                  setState({});
                  setQuery({ ...query, cursor });
                }}
              >
                Next duplicate keys
              </Button>
            ) : null}
            {query.cursor || query.group_id ? (
              <Button
                type="button"
                variant="outline"
                onClick={() => {
                  setState({});
                  setQuery({ language: query.language, file: query.file });
                }}
              >
                Back to first page
              </Button>
            ) : null}
          </>
        )}
        <Button type="button" variant="outline" onClick={() => setOpen(false)}>
          Close diagnostics
        </Button>
      </DialogContent>
    </Dialog>
  );
}
