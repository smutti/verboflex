import { t, useUiLanguage } from "@/i18n";
import { useEffect, useId, useRef, useState, type FormEvent } from "react";
import {
  getAdminBitbucketWorkspace,
  updateAdminBitbucketWorkspace,
} from "../../../api/client";
import {
  Alert,
  AlertDescription,
  AlertTitle,
} from "../../../components/ui/alert";
import { Button } from "../../../components/ui/button";
import { Input } from "../../../components/ui/input";
import { Label } from "../../../components/ui/label";

export function BitbucketWorkspaceSettings({
  accessToken,
}: {
  accessToken: string;
}) {
  useUiLanguage();
  const inputId = useId();
  const [workspace, setWorkspace] = useState("");
  const [saved, setSaved] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [pending, setPending] = useState(false);
  const pendingRef = useRef(false);
  const [reload, setReload] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    queueMicrotask(() => {
      if (controller.signal.aborted) return;
      setLoading(true);
      setError(false);
      void getAdminBitbucketWorkspace({
        auth: accessToken,
        signal: controller.signal,
      })
        .then((result) => {
          if (controller.signal.aborted) return;
          if (!result.data) throw new Error();
          setWorkspace(result.data.workspace ?? "");
          setSaved(result.data.workspace ?? "");
          setLoading(false);
        })
        .catch(() => {
          if (!controller.signal.aborted) {
            setError(true);
            setLoading(false);
          }
        });
    });
    return () => controller.abort();
  }, [accessToken, reload]);
  async function save(event: FormEvent) {
    event.preventDefault();
    if (pendingRef.current) return;
    pendingRef.current = true;
    setPending(true);
    setError(false);
    try {
      const result = await updateAdminBitbucketWorkspace({
        auth: accessToken,
        body: { workspace: workspace.trim() },
      });
      if (!result.data) throw new Error();
      setWorkspace(result.data.workspace ?? "");
      setSaved(result.data.workspace ?? "");
    } catch {
      setError(true);
    } finally {
      pendingRef.current = false;
      setPending(false);
    }
  }
  return (
    <form
      onSubmit={(event) => void save(event)}
      className="grid gap-4 rounded-lg border bg-secondary p-6"
      aria-label={t("Bitbucket workspace")}
    >
      <h2 className="text-heading font-semibold">{t("Bitbucket workspace")}</h2>
      <p className="text-muted-foreground">
        {t("This workspace is shared by all products.")}
      </p>
      <div className="grid gap-2">
        <Label htmlFor={inputId}>{t("Workspace")}</Label>
        <Input
          id={inputId}
          required
          maxLength={100}
          autoComplete="off"
          value={workspace}
          placeholder={t("e.g. your-team")}
          disabled={loading || pending || saved === null}
          onChange={(event) => {
            setWorkspace(event.target.value);
            setError(false);
          }}
        />
      </div>
      {error ? (
        <Alert variant="destructive">
          <AlertTitle>{t("Workspace not saved")}</AlertTitle>
          <AlertDescription>
            {saved === null ? (
              <Button
                type="button"
                variant="outline"
                onClick={() => setReload((value) => value + 1)}
              >
                {t("Retry")}
              </Button>
            ) : (
              t("Enter the workspace slug and try again.")
            )}
          </AlertDescription>
        </Alert>
      ) : null}
      <div className="flex flex-wrap items-center gap-3">
        <Button
          type="submit"
          disabled={loading || pending || saved === null || workspace === saved}
        >
          {pending ? t("Saving…") : t("Save workspace")}
        </Button>
        {!loading && saved && workspace === saved ? (
          <span role="status" className="text-sm text-muted-foreground">
            {t("Configured workspace: ")}
            {saved}
          </span>
        ) : null}
      </div>
    </form>
  );
}
