import { useEffect, useState } from "react";
import {
  cancelTranslationScreenshot,
  getTranslationCodeContext,
  getTranslationScreenshot,
  getTranslationScreenshotImage,
  listTranslationScreenshots,
  requestTranslationScreenshot,
  type CodeContextResponse,
  type ScreenshotResponse,
} from "../../api/client";
import { Button } from "../../components/ui/button";
import { Label } from "../../components/ui/label";

const active = (job: ScreenshotResponse | null) =>
  job?.state === "queued" || job?.state === "rendering";

export function TranslationScreenshots({
  accessToken,
  groupId,
  dirty,
  proposalVersion,
}: {
  accessToken: string;
  groupId: string;
  dirty: boolean;
  proposalVersion?: number;
}) {
  const [context, setContext] = useState<CodeContextResponse | null>(null);
  const [job, setJob] = useState<ScreenshotResponse | null>(null);
  const [selected, setSelected] = useState("");
  const [theme, setTheme] = useState<"light" | "dark">("light");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [image, setImage] = useState("");
  const [retry, setRetry] = useState(0);
  const [pending, setPending] = useState<{
    id: string;
    preview: string;
    theme: "light" | "dark";
    version?: number;
  } | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    void Promise.all([
      getTranslationCodeContext({
        auth: accessToken,
        path: { group_id: groupId },
        signal: controller.signal,
      }),
      listTranslationScreenshots({
        auth: accessToken,
        path: { group_id: groupId },
        signal: controller.signal,
      }),
    ])
      .then(([source, captures]) => {
        if (controller.signal.aborted) return;
        if (!source.data || !captures.data)
          throw new Error("Screenshot context unavailable");
        setContext(source.data);
        setJob(
          [...captures.data.items].sort((a, b) =>
            b.created_at.localeCompare(a.created_at),
          )[0] ?? null,
        );
        setError("");
      })
      .catch(() => {
        if (!controller.signal.aborted)
          setError("Could not load screenshots. Retry to reconnect.");
      });
    return () => controller.abort();
  }, [accessToken, groupId, retry]);
  const jobId = job?.id;
  const jobState = job?.state;
  useEffect(() => {
    if (!jobId || (jobState !== "queued" && jobState !== "rendering")) return;
    const controller = new AbortController();
    const timer = window.setInterval(() => {
      void getTranslationScreenshot({
        auth: accessToken,
        path: { group_id: groupId, job_id: jobId },
        signal: controller.signal,
      })
        .then((result) => {
          if (controller.signal.aborted) return;
          if (!result.data) throw new Error("Capture unavailable");
          setJob(result.data);
        })
        .catch(() => {
          if (!controller.signal.aborted)
            setError(
              "Connection interrupted. Your capture remains available after reconnecting.",
            );
        });
    }, 2000);
    return () => {
      controller.abort();
      window.clearInterval(timer);
    };
  }, [accessToken, groupId, jobId, jobState]);
  useEffect(() => {
    if (!jobId || jobState !== "succeeded") return;
    const controller = new AbortController();
    let url = "";
    void getTranslationScreenshotImage({
      auth: accessToken,
      path: { group_id: groupId, job_id: jobId },
      parseAs: "blob",
      signal: controller.signal,
    })
      .then((result) => {
        if (controller.signal.aborted) return;
        if (!(result.data instanceof Blob))
          throw new Error("Image unavailable");
        url = URL.createObjectURL(result.data);
        setImage(url);
      })
      .catch(() => {
        if (!controller.signal.aborted)
          setError("The image is unavailable or its access has expired.");
      });
    return () => {
      controller.abort();
      if (url) URL.revokeObjectURL(url);
    };
  }, [accessToken, groupId, jobId, jobState, retry]);
  const available = [
    ...new Set((context?.previews ?? []).map((p) => p.function)),
  ].filter((name) => context?.capture_functions.includes(name));
  const preview = selected || available[0] || "";
  async function capture() {
    if (dirty || busy || active(job) || !preview) return;
    const request = pending ?? {
      id: crypto.randomUUID(),
      preview,
      theme,
      version: proposalVersion,
    };
    setPending(request);
    setBusy(true);
    setError("");
    setImage("");
    try {
      const result = await requestTranslationScreenshot({
        auth: accessToken,
        path: { group_id: groupId, job_id: request.id },
        body: {
          preview_function: request.preview,
          theme: request.theme,
          proposal_version: request.version ?? null,
        },
      });
      if (!result.data) {
        if (
          result.response &&
          result.response.status >= 400 &&
          result.response.status < 500
        )
          setPending(null);
        const detail =
          result.error && "detail" in result.error ? result.error.detail : null;
        throw new Error(
          typeof detail === "string" ? detail : "Capture request failed",
        );
      }
      setJob(result.data);
      setPending(null);
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : "Capture request failed",
      );
    } finally {
      setBusy(false);
    }
  }
  async function cancel() {
    if (!job) return;
    try {
      const result = await cancelTranslationScreenshot({
        auth: accessToken,
        path: { group_id: groupId, job_id: job.id },
      });
      if (result.data) setJob(result.data);
      else setError("Could not cancel this capture.");
    } catch {
      setError("Could not cancel this capture. Reconnect to check its status.");
    }
  }
  return (
    <section aria-label="Compose screenshots" className="space-y-4 pt-4">
      {error && (
        <p role="alert">
          {error}{" "}
          <Button variant="outline" onClick={() => setRetry((n) => n + 1)}>
            Reconnect
          </Button>
        </p>
      )}
      {!context && !error && <p role="status">Loading code context…</p>}
      {context && !context.configured && (
        <p>
          No application code repository is configured for this translation.
        </p>
      )}
      {context?.configured && (
        <>
          <p className="text-sm text-muted-foreground">
            Code references indicate possible usage. The selected preview shows
            one fixture state.
          </p>
          <ul className="space-y-1 text-sm">
            {context.occurrences.map((item, index) => (
              <li
                className="wrap-anywhere"
                key={`${item.path}:${item.line}:${index}`}
              >
                {item.path}:{item.line} ·{" "}
                {item.function?.split(".").pop() ?? item.symbol}
              </li>
            ))}
          </ul>
          {context.occurrences_truncated && (
            <p>Showing the first 100 references.</p>
          )}
          {available.length === 0 ? (
            <p>
              No callable Compose preview is registered for this key. Ask the
              project administrator to register a fixture preview.
            </p>
          ) : (
            <>
              <Label className="grid gap-2">
                Screen preview
                <select
                  className="rounded-md border bg-background p-2"
                  value={preview}
                  onChange={(e) => setSelected(e.target.value)}
                  disabled={busy || active(job) || pending !== null}
                >
                  {available.map((name) => (
                    <option key={name} value={name}>
                      {name.split(".").pop()}
                    </option>
                  ))}
                </select>
              </Label>
              <Label className="grid gap-2">
                Appearance
                <select
                  className="rounded-md border bg-background p-2"
                  value={theme}
                  onChange={(e) => setTheme(e.target.value as "light" | "dark")}
                  disabled={busy || active(job) || pending !== null}
                >
                  <option value="light">Light</option>
                  <option value="dark">Dark</option>
                </select>
              </Label>
              {dirty && (
                <p>
                  Save your translation changes before requesting a screenshot.
                </p>
              )}
              <Button
                onClick={() => void capture()}
                disabled={dirty || busy || active(job)}
              >
                {busy
                  ? "Requesting…"
                  : pending
                    ? "Retry capture request"
                    : "Generate screenshot"}
              </Button>
              <p className="text-sm text-muted-foreground">
                {proposalVersion
                  ? `Includes saved proposal version ${proposalVersion}.`
                  : "Uses the imported translations."}{" "}
                A new request renders a fresh image.
              </p>
            </>
          )}
          {job && (
            <div className="space-y-2">
              <p role="status">
                Screenshot: {job.state}
                {job.error_code
                  ? ` · ${job.error_code.replaceAll("_", " ")}`
                  : ""}
              </p>
              {active(job) && (
                <Button variant="outline" onClick={() => void cancel()}>
                  Cancel capture
                </Button>
              )}
              {job.state === "succeeded" && image && (
                <a href={image} target="_blank" rel="noreferrer">
                  <img
                    src={image}
                    alt="Compose screen preview with the selected translations"
                    className="h-auto w-full rounded-md border"
                  />
                </a>
              )}
              <p className="text-xs text-muted-foreground">
                {job.request.proposal_version
                  ? `Captured proposal version ${job.request.proposal_version}. `
                  : "Captured imported translations. "}
                Created {new Date(job.created_at).toLocaleString()} · Expires{" "}
                {new Date(job.expires_at).toLocaleDateString()}
              </p>
            </div>
          )}
        </>
      )}
    </section>
  );
}
