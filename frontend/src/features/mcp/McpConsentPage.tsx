import { t, useUiLanguage } from "@/i18n";
import { useState } from "react";
import { useMcpData } from "./useMcpData";
import { useSearchParams } from "react-router-dom";
import { Plug } from "lucide-react";
import { Button } from "../../components/ui/button";
import { mcpRequest } from "./api";

type Consent = {
  client_name: string;
  redirect_origin: string;
  scopes: string[];
};

export function McpConsentPage({
  accessToken,
  account,
  onSignOut,
}: {
  accessToken: string;
  account?: string;
  onSignOut?: () => Promise<void>;
}) {
  useUiLanguage();
  const [params] = useSearchParams();
  const requestId = params.get("request") ?? "";
  const [allowWrite, setAllowWrite] = useState(false);
  const path = `/authorization/${encodeURIComponent(requestId)}`;
  const consent = useMcpData<Consent>(accessToken, path);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<Error>();
  async function decide(allow: boolean) {
    setBusy(true);
    setError(undefined);
    try {
      const result = await mcpRequest<{ redirect_url: string }>(
        accessToken,
        path,
        {
          method: "POST",
          body: JSON.stringify({ allow, allow_write: allowWrite }),
        },
      );
      window.location.assign(result.redirect_url);
    } catch (failure) {
      setError(
        failure instanceof Error ? failure : new Error("Connection failed."),
      );
      setBusy(false);
    }
  }
  return (
    <main className="mx-auto grid min-h-screen max-w-lg content-center gap-5 px-6 py-12">
      <Plug aria-hidden="true" className="size-9 text-primary" />
      <h1 className="text-display font-semibold">
        {t("Connect to VerboFlex")}
      </h1>
      {account && (
        <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
          <span className="break-all">{account}</span>
          {onSignOut && (
            <Button
              variant="ghost"
              size="sm"
              disabled={busy}
              onClick={() => void onSignOut()}
            >
              {t("Use another account")}
            </Button>
          )}
        </div>
      )}
      {consent.isPending && <p role="status">{t("Loading request…")}</p>}
      {(consent.error || error) && (
        <p role="alert" className="text-destructive">
          {(consent.error || error)?.message}
        </p>
      )}
      {consent.data && (
        <section className="grid gap-5 rounded-lg border bg-card p-6 shadow-sm">
          <div className="grid gap-2">
            <h2 className="text-heading font-semibold break-words">
              {consent.data.client_name}
            </h2>
            <p className="text-sm text-muted-foreground">
              {t("Check the callback address before connecting.")}
            </p>
            <code className="break-all text-sm">
              {consent.data.redirect_origin}
            </code>
          </div>
          <p>
            {t(
              "Read projects, translations and activity available to your account.",
            )}
          </p>
          {consent.data.scopes.includes("verboflex:write") && (
            <label className="flex items-start gap-3">
              <input
                type="checkbox"
                checked={allowWrite}
                onChange={(event) => setAllowWrite(event.target.checked)}
                className="mt-1 size-4 accent-primary"
              />
              <span>
                {t(
                  "Allow changes and repository actions permitted by my role.",
                )}
              </span>
            </label>
          )}
          <div className="flex flex-wrap justify-end gap-3">
            <Button
              variant="outline"
              disabled={busy}
              onClick={() => void decide(false)}
            >
              {t("Deny")}
            </Button>
            <Button disabled={busy} onClick={() => void decide(true)}>
              {busy ? t("Connecting…") : t("Connect")}
            </Button>
          </div>
        </section>
      )}
    </main>
  );
}
