import { t, useUiLanguage, getUiLanguage } from "@/i18n";
import { useEffect, useState } from "react";
import { ImageIcon, LoaderCircle } from "lucide-react";
import {
  cancelTranslationScreenshot,
  getTranslationCodeContext,
  getTranslationScreenshot,
  getTranslationScreenshotImage,
  listTranslationScreenshots,
  requestTranslationScreenshot,
  type CodeContextResponse,
  type ScreenshotResponse,
  type ScreenshotRequest,
} from "../../api/client";
import { Button } from "../../components/ui/button";
import { Label } from "../../components/ui/label";
import { ScreenshotImage } from "./ScreenshotImage";

const active = (job: ScreenshotResponse | null) =>
  job?.state === "queued" || job?.state === "rendering";

function ElapsedTime({ since }: { since: string }) {
  useUiLanguage();
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, []);
  const seconds = Math.max(0, Math.floor((now - Date.parse(since)) / 1000));
  return (
    <p className="text-sm" aria-live="off">
      {t("Elapsed: ")}
      {Math.floor(seconds / 60)}
      {t("m ")}
      {seconds % 60}
      {t("s")}
    </p>
  );
}

function captureFailure(code: string | null) {
  switch (code) {
    case "render_timeout":
      return t("The screenshot took too long to generate. Try again.");
    case "queue_timeout":
      return t(
        "The screenshot service did not become available. Try again later.",
      );
    case "source_or_access_changed":
    case "input_changed":
      return t(
        "The source or your access changed. Refresh this page before trying again.",
      );
    case "worker_interrupted":
      return t("Screenshot generation was interrupted. Try again.");
    default:
      return t(
        "The screenshot could not be generated. Try again or contact your project administrator.",
      );
  }
}

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
  useUiLanguage();
  const [context, setContext] = useState<CodeContextResponse | null>(null);
  const [job, setJob] = useState<ScreenshotResponse | null>(null);
  const [selected, setSelected] = useState("");
  const [theme, setTheme] = useState<"light" | "dark">("light");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [image, setImage] = useState<{ jobId: string; url: string } | null>(
    null,
  );
  const [retry, setRetry] = useState(0);
  const [targetId, setTargetId] = useState("");
  const [viewport, setViewport] = useState<"desktop" | "mobile">("desktop");
  const [pending, setPending] = useState<{
    id: string;
    body: ScreenshotRequest;
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
          setError("");
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
        setImage({ jobId, url });
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
  const legacy = [
    ...new Set((context?.previews ?? []).map((p) => p.function)),
  ].filter((name) => context?.capture_functions.includes(name));
  const web = context?.engine === "web";
  const targets = context?.web_targets ?? [];
  const target =
    targets.find((item) => item.value_id === targetId) ?? targets[0];
  const scenarios = (
    context?.scenarios ??
    legacy.map((name) => ({
      preview_function: name,
      label: name.split(".").pop() ?? name,
      explicit: false,
      scenario_id: null,
    }))
  ).filter(
    (scenario) =>
      !web || target?.scenario_ids.includes(scenario.scenario_id ?? ""),
  );
  const available = scenarios.map((scenario) =>
    web ? scenario.scenario_id! : scenario.preview_function!,
  );
  const preview = available.includes(selected) ? selected : available[0] || "";
  const stale =
    job?.state === "succeeded" &&
    (dirty ||
      (web &&
        (job.request.target_value_id !== target?.value_id ||
          job.request.viewport !== viewport ||
          job.request.scenario_id !== preview)) ||
      (job.request.proposal_version ?? null) !== (proposalVersion ?? null));
  async function capture() {
    if (dirty || busy || active(job) || !preview) return;
    const body: ScreenshotRequest = web
      ? {
          engine: "web",
          scenario_id: preview,
          target_value_id: target?.value_id,
          viewport,
          theme: "light",
          proposal_version: proposalVersion ?? null,
        }
      : {
          preview_function: preview,
          theme,
          proposal_version: proposalVersion ?? null,
        };
    const request = pending ?? { id: crypto.randomUUID(), body };
    setPending(request);
    setBusy(true);
    setError("");
    setImage(null);
    try {
      const result = await requestTranslationScreenshot({
        auth: accessToken,
        path: { group_id: groupId, job_id: request.id },
        body: request.body,
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
    <section
      aria-label={t(web ? "Web screenshots" : "Compose screenshots")}
      className="min-w-0 space-y-4"
    >
      {error && (
        <p role="alert">
          {t(error)}{" "}
          <Button variant="outline" onClick={() => setRetry((n) => n + 1)}>
            {t("Reconnect")}
          </Button>
        </p>
      )}
      {!context && !error && <p role="status">{t("Loading screenshots…")}</p>}
      {context && !context.configured && (
        <p>{t("Screenshots are not available for this translation.")}</p>
      )}
      {context?.configured && (
        <>
          {web && targets.length > 0 && (
            <>
              <Label className="grid gap-2">
                {t("Translation value")}
                <select
                  className="min-h-[44px] min-w-0 max-w-full rounded-md border bg-background p-2"
                  value={target?.value_id ?? ""}
                  disabled={busy || active(job) || pending !== null}
                  onChange={(e) => setTargetId(e.target.value)}
                >
                  {targets.map((item) => (
                    <option key={item.value_id} value={item.value_id}>
                      {JSON.stringify(item.json_path)}
                    </option>
                  ))}
                </select>
              </Label>
              <Label className="grid gap-2">
                {t("Viewport")}
                <select
                  className="min-h-[44px] rounded-md border bg-background p-2"
                  value={viewport}
                  disabled={busy || active(job) || pending !== null}
                  onChange={(e) =>
                    setViewport(e.target.value as "desktop" | "mobile")
                  }
                >
                  <option value="desktop">{t("Desktop")}</option>
                  <option value="mobile">{t("Mobile")}</option>
                </select>
              </Label>
            </>
          )}
          {scenarios.length > 0 && (
            <Label className="grid gap-2">
              {t("Screen scenario")}
              <select
                className="min-h-[44px] min-w-0 max-w-full rounded-md border bg-background p-2"
                value={preview}
                onChange={(e) => setSelected(e.target.value)}
                disabled={busy || active(job) || pending !== null}
              >
                {scenarios.map((scenario) => (
                  <option
                    key={scenario.scenario_id ?? scenario.preview_function}
                    value={scenario.scenario_id ?? scenario.preview_function}
                  >
                    {scenario.label}
                  </option>
                ))}
              </select>
            </Label>
          )}
          {!job && !busy && (
            <div className="space-y-2 rounded-md bg-muted p-4 text-center">
              <ImageIcon
                aria-hidden="true"
                className="mx-auto size-7 text-muted-foreground"
              />
              <p className="font-semibold">{t("No screenshot available")}</p>
              <p className="text-sm text-muted-foreground">
                {available.length > 0
                  ? t(
                      "Generate a screenshot to see the saved translation in context.",
                    )
                  : t("Screenshots are not available for this translation.")}
              </p>
            </div>
          )}
          {(busy || active(job)) && (
            <div className="space-y-2 rounded-md border bg-muted p-4">
              <p
                role="status"
                className="flex items-center gap-2 font-semibold"
              >
                <LoaderCircle
                  aria-hidden="true"
                  className="size-5 shrink-0 animate-spin motion-reduce:animate-none"
                />
                {busy
                  ? t("Requesting screenshot…")
                  : job?.state === "queued"
                    ? t("Waiting to generate screenshot…")
                    : t("Generating screenshot…")}
              </p>
              {job && active(job) && (
                <ElapsedTime key={job.id} since={job.created_at} />
              )}
              <p className="text-sm text-muted-foreground">
                {t(
                  "This can take several minutes. You can leave this page and return to see the result.",
                )}
              </p>
              {active(job) && (
                <Button variant="outline" onClick={() => void cancel()}>
                  {t("Cancel capture")}
                </Button>
              )}
            </div>
          )}
          {job && !busy && !active(job) && (
            <div className="space-y-2">
              <p role="status">
                {job.state === "succeeded"
                  ? image?.jobId === job.id
                    ? t("Screenshot ready")
                    : error
                      ? t("Screenshot generated. Reconnect to load the image.")
                      : t("Loading screenshot…")
                  : job.state === "failed"
                    ? captureFailure(job.error_code)
                    : job.state === "cancelled"
                      ? t("Screenshot cancelled. You can generate another one.")
                      : t("This screenshot has expired. Generate a new one.")}
              </p>
              {stale && (
                <p className="rounded-md bg-warning/10 p-3 text-sm text-warning">
                  {t(
                    "This screenshot does not show your latest changes. Save your translation and generate a new screenshot to update it.",
                  )}
                </p>
              )}
              {job.state === "succeeded" && image?.jobId === job.id && (
                <>
                  {(job.request.scenario_id ?? job.request.preview_function) !==
                    preview && (
                    <p className="text-sm font-medium">
                      {t("Captured scenario: {{scenario}}", {
                        scenario:
                          scenarios.find(
                            (scenario) =>
                              (scenario.scenario_id ??
                                scenario.preview_function) ===
                              (job.request.scenario_id ??
                                job.request.preview_function),
                          )?.label ??
                          (
                            job.request.scenario_id ??
                            job.request.preview_function
                          )
                            ?.split(".")
                            .pop() ??
                          "",
                      })}
                    </p>
                  )}
                  <ScreenshotImage
                    key={job.id}
                    url={image.url}
                    location={job.location}
                    stale={stale}
                  />
                  <p className="text-xs text-muted-foreground">
                    {job.request.proposal_version
                      ? t("Saved proposal version {{v0}}", {
                          v0: job.request.proposal_version,
                        })
                      : t("Imported translations")}{" "}
                    · {new Date(job.created_at).toLocaleString(getUiLanguage())}
                  </p>
                </>
              )}
            </div>
          )}
          <details className="min-w-0 text-sm">
            <summary className="min-h-[44px] cursor-pointer text-muted-foreground">
              {t("Screenshot options")}
            </summary>
            <div className="space-y-4 pt-2">
              {job?.receipt?.application_commit &&
                job.receipt.application_commit !== job.receipt.commit && (
                  <dl className="space-y-1 wrap-anywhere">
                    <dt>{t("Reviewed application revision")}</dt>
                    <dd>
                      <code>{job.receipt.application_commit}</code>
                    </dd>
                    <dt>{t("Language catalog revision")}</dt>
                    <dd>
                      <code>{job.receipt.commit}</code>
                    </dd>
                  </dl>
                )}
              {(context.diagnostics?.length ?? 0) > 0 && (
                <ul>
                  {context.diagnostics?.map((message) => (
                    <li key={message}>{message}</li>
                  ))}
                </ul>
              )}
              <details className="text-sm">
                <summary className="cursor-pointer text-muted-foreground">
                  {t("Code references (")}
                  {context.occurrences.length}
                  {context.occurrences_truncated ? "+" : ""})
                </summary>
                <ul className="space-y-1 pt-2">
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
                  <p>{t("Showing the first 100 references.")}</p>
                )}
              </details>
              {!web && available.length > 0 && (
                <>
                  <Label className="grid gap-2">
                    {t("Appearance")}
                    <select
                      className="rounded-md border bg-background p-2"
                      value={theme}
                      onChange={(e) =>
                        setTheme(e.target.value as "light" | "dark")
                      }
                      disabled={busy || active(job) || pending !== null}
                    >
                      <option value="light">{t("Light")}</option>
                      <option value="dark">{t("Dark")}</option>
                    </select>
                  </Label>
                </>
              )}
            </div>
          </details>
          {available.length > 0 && (
            <>
              {dirty && (
                <p>
                  {t(
                    "Save your translation changes before requesting a screenshot.",
                  )}
                </p>
              )}
              <Button
                onClick={() => void capture()}
                disabled={dirty || busy || active(job)}
              >
                {(busy || active(job)) && (
                  <LoaderCircle
                    aria-hidden="true"
                    className="size-4 animate-spin motion-reduce:animate-none"
                  />
                )}
                {busy
                  ? t("Requesting…")
                  : active(job)
                    ? t("Generating screenshot…")
                    : pending
                      ? t("Retry capture request")
                      : t("Generate screenshot")}
              </Button>
              <p className="text-sm text-muted-foreground">
                {proposalVersion
                  ? t("Includes saved proposal version {{v0}}.", {
                      v0: proposalVersion,
                    })
                  : t("Uses the imported translations.")}{" "}
                {t("The preview shows an example screen state.")}
              </p>
            </>
          )}
        </>
      )}
    </section>
  );
}
