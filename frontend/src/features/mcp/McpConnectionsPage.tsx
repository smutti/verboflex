import { t, useUiLanguage, getUiLanguage } from "@/i18n";
import { useState } from "react";
import { useMcpData } from "./useMcpData";
import { Button } from "../../components/ui/button";
import { mcpRequest } from "./api";

type Connection = {
  id: string;
  client_name: string;
  scopes: string[];
  created_at: string;
  expires_at: string;
};

export function McpConnectionsPage({ accessToken }: { accessToken: string }) {
  useUiLanguage();
  const connections = useMcpData<{ items: Connection[] }>(
    accessToken,
    "/connections",
  );
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<Error>();
  async function revoke(id: string) {
    setBusy(true);
    setError(undefined);
    try {
      await mcpRequest<void>(accessToken, `/connections/${id}`, {
        method: "DELETE",
      });
      connections.refetch();
    } catch (failure) {
      setError(
        failure instanceof Error ? failure : new Error("Revocation failed."),
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="grid max-w-3xl gap-5">
      <h1 className="text-display font-semibold">{t("Connected apps")}</h1>
      {connections.isPending && <p role="status">{t("Loading apps…")}</p>}
      {(connections.error || error) && (
        <div role="alert" className="grid gap-2 text-destructive">
          <p>{(connections.error || error)?.message}</p>
          <Button variant="outline" onClick={() => void connections.refetch()}>
            {t("Retry")}
          </Button>
        </div>
      )}
      {connections.data?.items.length === 0 && <p>{t("No connected apps.")}</p>}
      {connections.data?.items.map((app) => (
        <article
          key={app.id}
          className="flex flex-wrap items-center justify-between gap-4 rounded-lg border bg-card p-5"
        >
          <div className="grid min-w-0 gap-1">
            <h2 className="font-semibold break-words">{app.client_name}</h2>
            <p>
              {app.scopes.includes("verboflex:write")
                ? t("Read and write")
                : t("Read only")}
            </p>
            <p className="text-sm text-muted-foreground">
              {t("Expires ")}
              {new Date(app.expires_at).toLocaleDateString(getUiLanguage())}
            </p>
          </div>
          <Button
            variant="destructive"
            disabled={busy}
            onClick={() => void revoke(app.id)}
          >
            {t("Revoke access")}
          </Button>
        </article>
      ))}
    </section>
  );
}
