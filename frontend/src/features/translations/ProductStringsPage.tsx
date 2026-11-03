import { useEffect, useState, type ReactNode } from "react";
import { useOutletContext } from "react-router-dom";
import {
  listHtmlTemplates,
  type HtmlTemplateCatalog,
  type HtmlTemplateOption,
} from "@/api/client";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { t, useUiLanguage } from "@/i18n";
import type { TranslationsWorkspaceContext } from "./TranslationsWorkspace";
import { TranslationSearchPage } from "./TranslationSearchPage";
import { EmailTemplateWorkspace } from "./EmailTemplateWorkspace";
import {
  loadEmailWorkspaceView,
  saveEmailWorkspaceView,
  type EmailWorkspaceView,
} from "./translationPreferences";

const emailSelectClass =
  "min-h-11 max-w-full rounded-md border bg-background px-3 py-2 text-body font-regular";

function ProjectEditor({ context }: { context: TranslationsWorkspaceContext }) {
  useUiLanguage();
  const productId = context.lockedProduct!.id;
  const [preference, setPreference] = useState(() =>
    loadEmailWorkspaceView(context.principal.id, productId),
  );
  const [attempt, setAttempt] = useState(0);
  const identity = JSON.stringify([context.accessToken, productId, attempt]);
  const [catalog, setCatalog] = useState<{
    identity: string;
    data?: HtmlTemplateCatalog;
    failed?: boolean;
  } | null>(null);
  const [loadingMore, setLoadingMore] = useState(false);
  const [moreError, setMoreError] = useState(false);
  const [editorBusy, setEditorBusy] = useState(false);
  const data = catalog?.identity === identity ? catalog.data : undefined;
  const failed = catalog?.identity === identity && catalog.failed;
  useEffect(() => {
    const controller = new AbortController();
    void listHtmlTemplates({
      auth: context.accessToken,
      path: { product_id: productId },
      signal: controller.signal,
    })
      .then((result) => {
        if (controller.signal.aborted) return;
        if (!result.data) throw new Error("Email catalog unavailable");
        setCatalog({ identity, data: result.data });
      })
      .catch(() => {
        if (!controller.signal.aborted) setCatalog({ identity, failed: true });
      });
    return () => controller.abort();
  }, [context.accessToken, productId, identity]);
  const hasTemplates = Boolean(data?.items.length);
  const view = hasTemplates ? (preference ?? "email") : "strings";
  const control: ReactNode = hasTemplates ? (
    <div className="flex min-w-0 flex-col gap-1">
      <Label htmlFor="product-editor-view">{t("Project view")}</Label>
      <select
        id="product-editor-view"
        className={emailSelectClass}
        value={view}
        disabled={editorBusy}
        onChange={(event) => {
          const next = event.target.value as EmailWorkspaceView;
          const trigger = event.currentTarget;
          context.runDraftGuardedAction(() => {
            context.setActiveDraft(null);
            setPreference(next);
            saveEmailWorkspaceView(context.principal.id, productId, next);
          }, trigger);
        }}
      >
        <option value="email">{t("Email editor")}</option>
        <option value="strings">{t("String list")}</option>
      </select>
    </div>
  ) : null;
  async function loadMore() {
    if (!data?.next_cursor || loadingMore) return;
    setLoadingMore(true);
    setMoreError(false);
    try {
      const result = await listHtmlTemplates({
        auth: context.accessToken,
        path: { product_id: productId },
        query: { after: data.next_cursor },
      });
      if (!result.data || result.data.next_cursor === data.next_cursor)
        throw new Error("Invalid catalog page");
      const next = result.data;
      setCatalog((current) =>
        current?.identity === identity && current.data
          ? {
              identity,
              data: {
                items: [
                  ...new Map(
                    [...current.data.items, ...next.items].map(
                      (item: HtmlTemplateOption) => [item.group_id, item],
                    ),
                  ).values(),
                ],
                next_cursor: next.next_cursor,
              },
            }
          : current,
      );
    } catch {
      setMoreError(true);
    } finally {
      setLoadingMore(false);
    }
  }
  if (!data && !failed && preference !== "strings")
    return <p role="status">{t("Loading email templates…")}</p>;
  return (
    <div className="min-w-0 space-y-4">
      {failed && (
        <div
          role="status"
          className="flex flex-wrap items-center gap-3 text-label text-muted-foreground"
        >
          <span>{t("Email templates could not be loaded")}</span>
          <Button variant="outline" onClick={() => setAttempt((v) => v + 1)}>
            {t("Retry")}
          </Button>
        </div>
      )}
      {view === "email" && data ? (
        <EmailTemplateWorkspace
          context={context}
          templates={data.items}
          viewControl={control}
          onBusyChange={setEditorBusy}
        />
      ) : (
        <>
          {control && <div className="flex justify-end">{control}</div>}
          <TranslationSearchPage />
        </>
      )}
      {view === "email" && data?.next_cursor && (
        <div className="space-y-2">
          {moreError && (
            <p role="alert">{t("Email templates could not be loaded")}</p>
          )}
          <Button
            variant="outline"
            disabled={loadingMore}
            onClick={() => void loadMore()}
          >
            {loadingMore
              ? t("Loading email templates…")
              : t("Load more templates")}
          </Button>
        </div>
      )}
    </div>
  );
}

export function ProductStringsPage() {
  const context = useOutletContext<TranslationsWorkspaceContext>();
  return context.lockedProduct ? (
    <ProjectEditor
      key={`${context.principal.id}:${context.lockedProduct.id}`}
      context={context}
    />
  ) : (
    <TranslationSearchPage />
  );
}
