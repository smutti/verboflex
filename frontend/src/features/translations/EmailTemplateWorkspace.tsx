import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { Link } from "react-router-dom";
import {
  ArrowLeft,
  ArrowRight,
  FolderOpen,
  LockKeyhole,
  Mail,
  ShieldCheck,
} from "lucide-react";
import {
  getHtmlEditorDocument,
  getTranslationGroup,
  type HtmlEditorDocument,
  type HtmlEditorFragment,
  type HtmlTemplateOption,
  type TranslationGroupDetailResponse,
  type TranslationProposalConflictResponse,
  type TranslationProposalResponse,
} from "@/api/client";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { displayLanguage, t, useUiLanguage } from "@/i18n";
import { rolesForProduct } from "../auth/productRoles";
import type { TranslationsWorkspaceContext } from "./TranslationsWorkspace";
import {
  createActiveTranslationDraft,
  TranslationEditor,
  writableTranslationDetail,
  type ActiveTranslationDraft,
} from "./TranslationEditor";
import { completeTranslationDetail } from "./translationDetailAuthority";
import { TranslationConflictDialog } from "./TranslationConflictDialog";
import { TranslationStatusBadge } from "./TranslationStatusBadge";
import {
  InteractiveEmailCanvas,
  hasEditableHtmlText,
} from "./InteractiveEmailCanvas";

const selectClass =
  "min-h-11 max-w-full rounded-md border bg-background px-3 py-2 text-body font-regular";
const familyId = (item: HtmlTemplateOption) =>
  JSON.stringify([item.scope_id, item.name]);
const templateLabel = (name: string) =>
  name.split("/").at(-1)!.replace(/[-_]+/g, " ");
function fragmentLabel(fragment: HtmlEditorFragment, index: number) {
  if (fragment.element === "title") return t("Email title");
  if (fragment.element === "a") return t("Button or link text");
  if (/^h[1-6]$/.test(fragment.element))
    return t("Heading {{v0}}", { v0: index + 1 });
  return t("Text {{v0}}", { v0: index + 1 });
}

function EmailDocument({
  context,
  option,
  onBusyChange,
}: {
  context: TranslationsWorkspaceContext;
  option: HtmlTemplateOption;
  onBusyChange: (busy: boolean) => void;
}) {
  useUiLanguage();
  const [attempt, setAttempt] = useState(0);
  const identity = JSON.stringify([
    context.accessToken,
    option.group_id,
    attempt,
  ]);
  const [loaded, setLoaded] = useState<{
    identity: string;
    data?: HtmlEditorDocument;
    failed?: boolean;
  } | null>(null);
  const document = loaded?.identity === identity ? loaded.data : undefined;
  const [selected, setSelected] = useState<string | null>(null);
  const [detailLoad, setDetailLoad] = useState<{
    id: string;
    detail?: TranslationGroupDetailResponse;
    failed?: boolean;
  } | null>(null);
  const [textOverrides, setTextOverrides] = useState<
    ReadonlyMap<string, string>
  >(() => new Map());
  const [conflict, setConflict] = useState<{
    draft: ActiveTranslationDraft;
    response: TranslationProposalConflictResponse;
  } | null>(null);
  const [saving, setSaving] = useState(false);
  const detailRequest = useRef<AbortController | null>(null);
  const [savedMessage, setSavedMessage] = useState(false);
  const contextRef = useRef(context);
  useEffect(() => {
    contextRef.current = context;
  }, [context]);
  useEffect(() => {
    const controller = new AbortController();
    void getHtmlEditorDocument({
      auth: context.accessToken,
      path: { translation_group_id: option.group_id },
      signal: controller.signal,
    })
      .then((result) => {
        if (controller.signal.aborted) return;
        const data = result.data;
        if (
          !data ||
          data.product_id !== context.lockedProduct?.id ||
          data.language !== option.language ||
          data.path !== option.path ||
          !data.fragments.length ||
          data.fragments.some(
            (f) => !f.marker || !data.document.includes(f.marker),
          )
        )
          throw new Error("Email unavailable");
        setLoaded({ identity, data });
        const active = contextRef.current.activeDraft;
        const initial =
          data.fragments.find(
            (f) => f.group_id === active?.translationGroupId,
          ) ??
          data.fragments.find(
            (f) => f.element !== "title" && hasEditableHtmlText(f.text),
          ) ??
          data.fragments[0];
        setSelected(initial.group_id);
      })
      .catch(() => {
        if (!controller.signal.aborted) setLoaded({ identity, failed: true });
      });
    return () => {
      controller.abort();
      detailRequest.current?.abort();
    };
  }, [
    context.accessToken,
    context.lockedProduct?.id,
    identity,
    option.group_id,
    option.language,
    option.path,
  ]);
  const loadDetail = useCallback(
    (id: string) => {
      detailRequest.current?.abort();
      const controller = new AbortController();
      detailRequest.current = controller;
      setDetailLoad({ id });
      void getTranslationGroup({
        auth: context.accessToken,
        path: { translation_group_id: id },
        signal: controller.signal,
      })
        .then((result) => {
          if (controller.signal.aborted) return;
          const detail = result.data;
          if (
            !detail ||
            !completeTranslationDetail(detail, id) ||
            detail.product_id !== context.lockedProduct?.id ||
            detail.language !== option.language ||
            detail.is_deleted ||
            detail.values.length !== 1 ||
            detail.values[0].provenance?.path !== option.path ||
            detail.values[0].provenance?.execution_id !== document?.execution_id
          )
            throw new Error("Text unavailable");
          setDetailLoad({ id, detail });
          const latest =
            detail.pending_change?.values[0]?.text ??
            detail.values[0].translated_text ??
            detail.values[0].source_text ??
            "";
          setTextOverrides((old) => new Map(old).set(id, latest));
          const canEdit = rolesForProduct(
            contextRef.current.principal,
            detail.product_id,
          ).some((role) =>
            ["admin", "product_manager_reviewer", "translator"].includes(role),
          );
          const field =
            detail.values[0].translated_text === null
              ? "source_text"
              : "translated_text";
          if (
            canEdit &&
            writableTranslationDetail(detail, field) &&
            hasEditableHtmlText(latest) &&
            contextRef.current.activeDraft?.translationGroupId !== id
          )
            contextRef.current.setActiveDraft(
              createActiveTranslationDraft(
                detail,
                contextRef.current.principal.id,
              ),
            );
        })
        .catch(() => {
          if (!controller.signal.aborted) setDetailLoad({ id, failed: true });
        });
    },
    [
      context.accessToken,
      context.lockedProduct?.id,
      document?.execution_id,
      option.language,
      option.path,
    ],
  );
  useEffect(() => {
    let cancelled = false;
    queueMicrotask(() => {
      if (!cancelled && selected && document) loadDetail(selected);
    });
    return () => {
      cancelled = true;
      detailRequest.current?.abort();
    };
  }, [selected, document, loadDetail]);
  const select = useCallback(
    (id: string) => {
      if (saving || id === selected) return;
      context.runDraftGuardedAction(() => {
        context.setActiveDraft(null);
        setSelected(id);
        setSavedMessage(false);
        setConflict(null);
      });
    },
    [context, saving, selected],
  );
  const editable =
    document?.fragments.filter((f) => hasEditableHtmlText(f.text)) ?? [];
  const fragment = document?.fragments.find((f) => f.group_id === selected);
  const index = editable.findIndex((f) => f.group_id === selected);
  const detail = detailLoad?.id === selected ? detailLoad.detail : undefined;
  const draft =
    context.activeDraft?.translationGroupId === selected
      ? context.activeDraft
      : null;
  const texts = useMemo(() => {
    const values = new Map(textOverrides);
    if (draft?.values[0])
      values.set(draft.translationGroupId, draft.values[0].text);
    return values;
  }, [textOverrides, draft]);
  function saved(projection: TranslationProposalResponse) {
    if (!draft || projection.translation_group_id !== selected) return;
    const fresh = {
      ...draft.detail,
      review_eligible: false,
      pending_change: {
        version: projection.version,
        state: projection.state,
        target_branch: projection.target_branch,
        target_integrated: projection.target_integrated,
        reconciliation_required: projection.reconciliation_required,
        updated_at: projection.updated_at,
        updated_by: projection.updated_by,
        values: projection.pending,
      },
    };
    context.setActiveDraft(
      createActiveTranslationDraft(fresh, context.principal.id),
    );
    setDetailLoad({ id: projection.translation_group_id, detail: fresh });
    setTextOverrides((old) =>
      new Map(old).set(
        projection.translation_group_id,
        projection.pending[0].text,
      ),
    );
    setSavedMessage(true);
    if (context.snapshot)
      context.setSnapshot({ ...context.snapshot, pages: [] });
  }
  if (!document)
    return (
      <div className="p-6">
        {loaded?.identity === identity && loaded.failed ? (
          <div role="alert" className="space-y-3">
            <p>{t("HTML preview could not be loaded")}</p>
            <Button variant="outline" onClick={() => setAttempt((v) => v + 1)}>
              {t("Retry")}
            </Button>
          </div>
        ) : (
          <p role="status">{t("Loading HTML template…")}</p>
        )}
      </div>
    );
  return (
    <>
      <section
        className="min-w-0 bg-background p-4 lg:p-6"
        aria-label={t("Email preview")}
      >
        <div className="mb-4 flex items-center justify-between gap-2 text-label text-muted-foreground">
          <span className="flex items-center gap-2">
            <Mail aria-hidden="true" className="size-4" />
            {t("Email preview")}
          </span>
          <span className="rounded border bg-secondary px-2 py-1">
            {displayLanguage(option.language)}
          </span>
        </div>
        <InteractiveEmailCanvas
          document={document}
          texts={texts}
          selectedId={selected}
          onSelect={select}
          disabled={saving}
        />
        <details className="mt-4 text-label">
          <summary className="cursor-pointer py-2">
            {t("Email texts ({{v0}})", { v0: editable.length })}
          </summary>
          <div className="mt-2 grid gap-2">
            {editable.map((item, i) => (
              <Button
                key={item.group_id}
                variant={item.group_id === selected ? "secondary" : "ghost"}
                className="h-auto min-h-11 justify-start whitespace-normal text-left"
                onClick={() => select(item.group_id)}
                disabled={saving}
                aria-pressed={item.group_id === selected}
              >
                {fragmentLabel(item, i)} ·{" "}
                {(texts.get(item.group_id) ?? item.text).slice(0, 100)}
              </Button>
            ))}
          </div>
        </details>
      </section>
      <section
        className="flex min-w-0 flex-col gap-5 border-t p-5 lg:border-t-0 lg:border-l"
        aria-label={t("Selected text editor")}
      >
        <div>
          <div className="mb-2 flex items-center gap-2 text-label text-primary">
            <span className="rounded border border-primary/30 bg-primary/5 px-2 py-1">
              {index >= 0 ? index + 1 : "—"}
            </span>
            {t("Selected text")}
            <span className="ml-auto text-muted-foreground">
              {index >= 0 ? `${index + 1} / ${editable.length}` : ""}
            </span>
          </div>
          <h3 className="text-heading font-semibold">
            {fragment
              ? fragmentLabel(fragment, Math.max(index, 0))
              : t("Selected text")}
          </h3>
        </div>
        {detail ? (
          <>
            <div>
              <p className="mb-2 flex items-center justify-between gap-2 text-label font-semibold">
                {t("Source · {{v0}}", {
                  v0: displayLanguage(detail.base_language ?? option.language),
                })}
                <LockKeyhole
                  aria-hidden="true"
                  className="size-4 text-muted-foreground"
                />
              </p>
              <p
                lang={detail.base_language ?? undefined}
                dir="auto"
                className="rounded-md border bg-background p-3 whitespace-pre-wrap wrap-anywhere"
              >
                {detail.values[0].source_text ?? t("Source text unavailable")}
              </p>
            </div>
            {detail.pending_change && (
              <TranslationStatusBadge proposal={detail.pending_change} />
            )}
            {draft ? (
              <TranslationEditor
                key={`${context.accessToken}:${draft.translationGroupId}`}
                accessToken={context.accessToken}
                draft={draft}
                onDraftChange={(next) => {
                  context.setActiveDraft(next);
                  setSavedMessage(false);
                }}
                onSaved={saved}
                onStop={() =>
                  context.runDraftGuardedAction(() => {
                    context.setActiveDraft(
                      createActiveTranslationDraft(
                        detail,
                        context.principal.id,
                      ),
                    );
                  })
                }
                onConflict={(response, local) => {
                  if (response.latest) setConflict({ response, draft: local });
                }}
                onSavingChange={(busy) => {
                  setSaving(busy);
                  onBusyChange(busy);
                }}
                compact
                email
              />
            ) : (
              <div className="space-y-2">
                <p className="text-label font-semibold">
                  {t("Translation · {{v0}}", {
                    v0: displayLanguage(option.language),
                  })}
                </p>
                <p
                  dir="auto"
                  lang={option.language}
                  className="whitespace-pre-wrap wrap-anywhere"
                >
                  {texts.get(detail.id) ?? fragment?.text}
                </p>
                <p className="text-label text-muted-foreground">
                  {t("Read-only translation")}
                </p>
              </div>
            )}
            {savedMessage && (
              <p role="status" className="text-label text-success">
                {t("Translation saved as Draft")}
              </p>
            )}
          </>
        ) : detailLoad?.id === selected && detailLoad.failed ? (
          <div role="alert" className="space-y-2">
            <p>{t("Translation editor could not be loaded")}</p>
            <Button
              variant="outline"
              onClick={() => selected && loadDetail(selected)}
            >
              {t("Reload editor")}
            </Button>
          </div>
        ) : (
          <p role="status">{t("Loading translation editor")}</p>
        )}
        <div className="flex flex-wrap gap-2">
          <Button
            variant="outline"
            className="flex-1"
            disabled={index <= 0 || saving}
            onClick={() => select(editable[index - 1].group_id)}
          >
            <ArrowLeft aria-hidden="true" />
            {t("Previous")}
          </Button>
          <Button
            variant="outline"
            className="flex-1"
            disabled={index < 0 || index >= editable.length - 1 || saving}
            onClick={() => select(editable[index + 1].group_id)}
          >
            {t("Next")}
            <ArrowRight aria-hidden="true" />
          </Button>
        </div>
        <p className="flex items-start gap-2 border-t pt-4 text-label text-muted-foreground">
          <ShieldCheck aria-hidden="true" className="size-4 shrink-0" />
          {t(
            "Edit text only. HTML tags, links and template variables are protected.",
          )}
        </p>
        {detail && (
          <Button variant="ghost" className="w-fit" asChild>
            <Link
              to={`${context.detailsBasePath}/${encodeURIComponent(detail.id)}`}
            >
              {t("Review and comments")}
            </Link>
          </Button>
        )}
        <details className="text-label text-muted-foreground">
          <summary className="cursor-pointer py-2">
            {t("Template details")}
          </summary>
          <p className="mt-2 break-all">{document.path}</p>
          <p className="mt-2">
            {t("Saved as a draft; publishing requires a pull request.")}
          </p>
        </details>
      </section>
      {conflict?.response.latest && (
        <TranslationConflictDialog
          open
          draft={conflict.draft}
          latest={conflict.response.latest}
          onKeepEditing={() => setConflict(null)}
          onReconcile={(next) => {
            context.setActiveDraft(next);
            setConflict(null);
          }}
        />
      )}
    </>
  );
}

export function EmailTemplateWorkspace({
  context,
  templates,
  viewControl,
  onBusyChange,
}: {
  context: TranslationsWorkspaceContext;
  templates: HtmlTemplateOption[];
  viewControl: ReactNode;
  onBusyChange: (busy: boolean) => void;
}) {
  const uiLanguage = useUiLanguage();
  const families = useMemo(
    () =>
      [...new Set(templates.map(familyId))]
        .map((id) => ({
          id,
          items: templates.filter((item) => familyId(item) === id),
        }))
        .sort((a, b) => a.items[0].name.localeCompare(b.items[0].name)),
    [templates],
  );
  const [chosen, setChosen] = useState<string | null>(null);
  const [language, setLanguage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const family = families.find((f) => f.id === chosen) ?? families[0];
  const option =
    family.items.find((item) => item.language === language) ??
    family.items.find(
      (item) =>
        item.language === uiLanguage && item.language !== item.base_language,
    ) ??
    family.items.find((item) => item.language !== item.base_language) ??
    family.items[0];
  return (
    <div className="min-w-0 overflow-hidden rounded-lg border bg-secondary shadow-sm">
      <div className="flex flex-wrap items-center gap-4 border-b p-5">
        <div className="min-w-0 flex-1 basis-48">
          <h2 className="text-heading font-semibold wrap-anywhere">
            {templateLabel(option.name)}
          </h2>
          <p className="mt-1 text-label text-muted-foreground">
            {t("Source · {{v0}}", {
              v0: displayLanguage(option.base_language ?? option.language),
            })}
          </p>
        </div>
        <div className="flex min-w-0 flex-col gap-1">
          <Label htmlFor="email-target-language">{t("Translate into")}</Label>
          <select
            id="email-target-language"
            className={selectClass}
            value={option.language}
            disabled={busy}
            onChange={(event) => {
              const value = event.target.value;
              context.runDraftGuardedAction(() => {
                context.setActiveDraft(null);
                setLanguage(value);
              }, event.currentTarget);
            }}
          >
            {family.items.map((item) => (
              <option key={item.group_id} value={item.language}>
                {displayLanguage(item.language)}
                {item.language === item.base_language
                  ? ` · ${t("Source")}`
                  : ""}
              </option>
            ))}
          </select>
        </div>
        {viewControl}
      </div>
      <div className="flex min-w-0 flex-col gap-2 border-b p-4 xl:hidden">
        <Label htmlFor="email-template-picker">{t("Email templates")}</Label>
        <select
          id="email-template-picker"
          className={selectClass}
          value={family.id}
          disabled={busy}
          onChange={(event) => {
            const next = event.target.value;
            if (next === family.id) return;
            context.runDraftGuardedAction(() => {
              context.setActiveDraft(null);
              setChosen(next);
            }, event.currentTarget);
          }}
        >
          {families.map((f) => (
            <option key={f.id} value={f.id}>
              {f.items[0].name.replace(/[-_]+/g, " ")}
            </option>
          ))}
        </select>
      </div>
      <div className="grid min-w-0 xl:grid-cols-[11rem_minmax(0,1fr)]">
        <aside
          className="hidden max-h-[75vh] min-w-0 flex-col gap-1 self-start overflow-y-auto border-r p-3 xl:flex"
          aria-label={t("Email templates")}
        >
          <h3 className="w-full px-2 py-1 text-label font-semibold text-muted-foreground">
            {t("Email templates")}
          </h3>
          {families.map((f) => {
            const first = f.items[0],
              folder = first.name.includes("/")
                ? first.name.slice(0, first.name.lastIndexOf("/"))
                : null;
            return (
              <Button
                key={f.id}
                variant="ghost"
                disabled={busy}
                aria-pressed={f.id === family.id}
                className={`h-auto min-h-11 min-w-0 max-w-full justify-start gap-2 border-l-4 px-2 py-3 text-left whitespace-normal ${f.id === family.id ? "border-l-primary bg-muted font-semibold" : "border-l-transparent"}`}
                onClick={(event) => {
                  if (f.id === family.id) return;
                  context.runDraftGuardedAction(() => {
                    context.setActiveDraft(null);
                    setChosen(f.id);
                  }, event.currentTarget);
                }}
              >
                <Mail className="size-4 shrink-0" aria-hidden="true" />
                <span className="min-w-0 wrap-anywhere">
                  {templateLabel(first.name)}
                  {folder && (
                    <span className="mt-1 flex items-center gap-1 text-label font-regular text-muted-foreground">
                      <FolderOpen aria-hidden="true" className="size-3" />
                      {folder}
                    </span>
                  )}
                  <span className="mt-1 block text-label font-regular text-muted-foreground">
                    {t("{{v0}} languages", { v0: f.items.length })}
                  </span>
                </span>
              </Button>
            );
          })}
        </aside>
        <div className="grid min-w-0 lg:grid-cols-[minmax(0,1fr)_minmax(17rem,21rem)]">
          <EmailDocument
            key={`${option.group_id}:${context.accessToken}`}
            context={context}
            option={option}
            onBusyChange={(saving) => {
              setBusy(saving);
              onBusyChange(saving);
            }}
          />
        </div>
      </div>
    </div>
  );
}
