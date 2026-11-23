import { useCallback, useEffect, useRef, useState } from "react";
import {
  approveAllAuthoringDrafts,
  getAuthoringApprovalPreview,
  type AuthoringApprovalPreview,
} from "../../api/client";
import { Button } from "../../components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogTitle,
  DialogDescription,
} from "../../components/ui/dialog";
import { t, useUiLanguage } from "@/i18n";

type Props = {
  accessToken: string;
  productId: string;
  revision: number;
  onCompleted: () => void;
};

export function BulkAuthoringApproval({
  accessToken,
  productId,
  revision,
  onCompleted,
}: Props) {
  useUiLanguage();
  const [preview, setPreview] = useState<AuthoringApprovalPreview | null>(null);
  const [open, setOpen] = useState(false);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const [refresh, setRefresh] = useState(0);
  const pending = preview?.latest?.state === "queued";
  const observed = useRef<string | null>(null);
  const attempt = useRef<{ fingerprint: string; id: string } | null>(null);
  const completed = useRef(onCompleted);
  useEffect(() => {
    completed.current = onCompleted;
  }, [onCompleted]);
  const reload = useCallback(() => setRefresh((v) => v + 1), []);

  useEffect(() => {
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout> | undefined;
    void getAuthoringApprovalPreview({
      auth: accessToken,
      path: { product_id: productId },
      signal: controller.signal,
    })
      .then((result) => {
        if (controller.signal.aborted) return;
        if (!result.data) throw new Error("preview");
        const value = result.data;
        setPreview(value);
        if (
          observed.current &&
          value.latest?.id === observed.current &&
          value.latest.state !== "queued"
        ) {
          observed.current = null;
          completed.current();
        }
        if (value.latest?.state === "queued")
          observed.current = value.latest.id;
        timer = setTimeout(
          reload,
          value.latest?.state === "queued" ? 3000 : 15000,
        );
      })
      .catch(() => {
        if (!controller.signal.aborted) {
          setError(
            t("Could not load bulk approval. Retry to check its status."),
          );
          timer = setTimeout(reload, 5000);
        }
      });
    return () => {
      controller.abort();
      clearTimeout(timer);
    };
  }, [accessToken, productId, revision, refresh, reload]);

  async function submit() {
    if (!preview || sending || pending) return;
    if (attempt.current?.fingerprint !== preview.fingerprint) {
      attempt.current = {
        fingerprint: preview.fingerprint,
        id: crypto.randomUUID(),
      };
    }
    setSending(true);
    setError("");
    try {
      const result = await approveAllAuthoringDrafts({
        auth: accessToken,
        path: { product_id: productId, request_id: attempt.current.id },
        body: { fingerprint: preview.fingerprint },
      });
      if (!result.data) {
        const detail =
          typeof result.error === "object" &&
          result.error !== null &&
          "detail" in result.error
            ? result.error.detail
            : null;
        setError(
          typeof detail === "string"
            ? detail
            : t("Could not start bulk approval. Retry to check its status."),
        );
        reload();
        return;
      }
      setPreview((current) =>
        current ? { ...current, latest: result.data! } : current,
      );
      observed.current = result.data.id;
      if (result.data.state === "failed") attempt.current = null;
      setOpen(false);
      reload();
    } catch {
      setError(t("Could not start bulk approval. Retry to check its status."));
      reload();
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="space-y-2">
      {((preview?.count ?? 0) > 0 || pending) && (
        <Button
          variant="outline"
          disabled={sending || pending}
          onClick={() => {
            setError("");
            // A known failed operation may be retried after correcting the drafts/source.
            if (preview?.latest?.state === "failed") attempt.current = null;
            setOpen(true);
            reload();
          }}
        >
          {pending ? t("Approving drafts…") : t("Approve all drafts")}
        </Button>
      )}
      {pending && (
        <p role="status" className="text-sm text-muted-foreground">
          {t("Approval is running on the server. You can leave this page.")}
        </p>
      )}
      {preview?.latest?.state === "succeeded" && (
        <p role="status" className="text-sm text-muted-foreground">
          {t("Last bulk approval: {{count}} entries.", {
            count: preview.latest.count,
          })}{" "}
          {preview.latest.delivery_state === "pending"
            ? t("Commits are in progress.")
            : preview.latest.delivery_state === "failed"
              ? t("A commit needs attention. Check Approval commits.")
              : preview.latest.delivery_state === "committed"
                ? t("Changes are saved on the working branch.")
                : t("No automatic commit workflow is configured.")}{" "}
          {preview.latest.catalog_state === "pending"
            ? t("The translation list is updating automatically.")
            : preview.latest.catalog_state === "failed"
              ? t(
                  "Catalog update failed. Saved translations are preserved. Open Update catalog.",
                )
              : preview.latest.catalog_state === "current"
                ? t("The translation list is up to date.")
                : null}
        </p>
      )}
      {preview?.latest?.state === "failed" && (
        <p role="alert" className="text-sm text-destructive">
          {t("Bulk approval failed. All selected drafts are unchanged.")}{" "}
          {preview.latest.error}
        </p>
      )}
      {error && !open && (
        <p role="alert" className="text-sm text-destructive">
          {error}{" "}
          <Button
            variant="ghost"
            onClick={() => {
              setError("");
              reload();
            }}
          >
            {t("Retry")}
          </Button>
        </p>
      )}
      <Dialog
        open={open}
        onOpenChange={(value) => {
          if (!sending) setOpen(value);
        }}
      >
        <DialogContent>
          <DialogTitle>{t("Approve all drafts?")}</DialogTitle>
          <DialogDescription>
            {t(
              "Approve every draft in this project, including entries on other pages. Saved translations and the base language stay unchanged. Commits use the configured working branches; no pull request is opened.",
            )}
          </DialogDescription>
          {preview && (
            <>
              <p>{t("{{count}} drafts selected", { count: preview.count })}</p>
              <ul className="max-h-40 overflow-auto">
                {Object.entries(preview.languages)
                  .sort()
                  .map(([language, count]) => (
                    <li key={language}>
                      {language}: {count}
                    </li>
                  ))}
              </ul>
              {preview.source_changed > 0 && (
                <p role="alert">
                  {t(
                    "{{count}} drafts have a changed source. Refresh the source before approving.",
                    { count: preview.source_changed },
                  )}
                </p>
              )}
              {preview.over_limit && (
                <p role="alert">
                  {t("Bulk approval supports up to 5000 drafts per project.")}
                </p>
              )}
            </>
          )}
          {error && (
            <p role="alert" className="text-sm text-destructive">
              {error}
            </p>
          )}
          <div className="flex flex-wrap justify-end gap-2">
            <Button
              variant="outline"
              disabled={sending}
              onClick={() => setOpen(false)}
            >
              {t("Cancel")}
            </Button>
            <Button
              disabled={
                !preview?.count ||
                sending ||
                pending ||
                preview.source_changed > 0 ||
                preview.over_limit
              }
              onClick={() => void submit()}
            >
              {sending ? t("Approving drafts…") : t("Confirm approval")}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
