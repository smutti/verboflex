import { t, useUiLanguage } from "@/i18n";
import { useEffect, useState } from "react";
import { BookOpen, Pencil, Trash2 } from "lucide-react";
import {
  deleteGlossaryTerm,
  listGlossaryTerms,
  saveGlossaryTerm,
  type GlossaryInput,
  type GlossaryResponse,
} from "../../api/client";
import { Button } from "../../components/ui/button";
import { Input } from "../../components/ui/input";
import { Label } from "../../components/ui/label";
import { SearchableSelect } from "../../components/ui/searchable-select";
import {
  Dialog,
  DialogContent,
  DialogTitle,
  DialogDescription,
} from "../../components/ui/dialog";
import {
  AlertDialog,
  AlertDialogContent,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogCancel,
  AlertDialogAction,
} from "../../components/ui/alert-dialog";

export function Glossary({
  accessToken,
  productId,
  canManage,
  languages,
}: {
  accessToken: string;
  productId: string;
  canManage: boolean;
  languages: { code: string; label: string }[];
}) {
  useUiLanguage();
  const [open, setOpen] = useState(false);
  return (
    <>
      <Button variant="outline" onClick={() => setOpen(true)}>
        <BookOpen className="size-4" />
        {t("Glossary")}
      </Button>
      {open && (
        <GlossaryDialog
          accessToken={accessToken}
          productId={productId}
          canManage={canManage}
          languages={languages}
          onClose={() => setOpen(false)}
        />
      )}
    </>
  );
}
function GlossaryDialog({
  accessToken,
  productId,
  canManage,
  languages,
  onClose,
}: {
  accessToken: string;
  productId: string;
  canManage: boolean;
  languages: { code: string; label: string }[];
  onClose: () => void;
}) {
  useUiLanguage();
  const [items, setItems] = useState<GlossaryResponse[]>([]);
  const [next, setNext] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [search, setSearch] = useState("");
  const [refresh, setRefresh] = useState(0);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState<{
    id: string;
    data: GlossaryInput;
  } | null>(null);
  const [dirty, setDirty] = useState(false);
  const [confirmation, setConfirmation] = useState<
    "close" | "cancel" | GlossaryResponse | null
  >(null);
  useEffect(() => {
    const handler = (e: BeforeUnloadEvent) => {
      if (dirty) {
        e.preventDefault();
        e.returnValue = "";
      }
    };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [dirty]);
  useEffect(() => {
    const controller = new AbortController();
    void Promise.resolve().then(async () => {
      if (controller.signal.aborted) return;
      setLoading(true);
      setError(null);
      try {
        const r = await listGlossaryTerms({
          auth: accessToken,
          path: { product_id: productId },
          query: { q: search },
          signal: controller.signal,
        });
        if (controller.signal.aborted) return;
        if (!r.data) throw new Error();
        setItems(r.data.items);
        setNext(r.data.next_after ?? null);
      } catch {
        if (!controller.signal.aborted)
          setError("Glossary could not be loaded");
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    });
    return () => controller.abort();
  }, [accessToken, productId, search, refresh]);
  const change = (data: Partial<GlossaryInput>) => {
    if (editing) {
      setEditing({ ...editing, data: { ...editing.data, ...data } });
      setDirty(true);
    }
  };
  async function save() {
    if (!editing || busy) return;
    setBusy(true);
    setError(null);
    try {
      const r = await saveGlossaryTerm({
        auth: accessToken,
        path: { product_id: productId, entry_id: editing.id },
        body: editing.data,
      });
      if (!r.data) {
        setError(
          r.response?.status === 409
            ? "This term changed or already exists. Reload the glossary."
            : "Term could not be saved",
        );
        return;
      }
      setEditing(null);
      setDirty(false);
      setRefresh((r) => r + 1);
    } catch {
      setError("Term could not be saved");
    } finally {
      setBusy(false);
    }
  }
  async function remove(item: GlossaryResponse) {
    setBusy(true);
    setError(null);
    try {
      const r = await deleteGlossaryTerm({
        auth: accessToken,
        path: { product_id: productId, entry_id: item.id },
        query: { expected_version: item.version },
      });
      if (r.response?.status !== 204) throw new Error();
      setRefresh((r) => r + 1);
    } catch {
      setError("Term could not be deleted. Reload the glossary.");
    } finally {
      setBusy(false);
    }
  }
  async function loadMore() {
    if (!next || busy) return;
    setBusy(true);
    try {
      const r = await listGlossaryTerms({
        auth: accessToken,
        path: { product_id: productId },
        query: { q: search, after: next },
      });
      if (!r.data) throw new Error();
      setItems((old) => [...old, ...r.data!.items]);
      setNext(r.data.next_after ?? null);
    } catch {
      setError("More terms could not be loaded");
    } finally {
      setBusy(false);
    }
  }
  const options = languages.map((l) => ({
    value: l.code,
    label: `${l.label} · ${l.code}`,
  }));
  for (const code of [
    editing?.data.source_language,
    editing?.data.target_language,
  ]) {
    if (code && !options.some((o) => o.value === code))
      options.push({ value: code, label: code });
  }
  return (
    <>
      <Dialog
        open
        onOpenChange={(value) => {
          if (!value && !busy) {
            if (dirty) setConfirmation("close");
            else onClose();
          }
        }}
      >
        <DialogContent className="sm:max-w-3xl max-h-[90vh] overflow-y-auto">
          <DialogTitle>{t("Glossary")}</DialogTitle>
          <DialogDescription className="sr-only">
            {t("Project terminology")}
          </DialogDescription>
          {error && (
            <p role="alert" className="text-destructive">
              {t(error)}{" "}
              <Button
                variant="ghost"
                onClick={() => setRefresh((r) => r + 1)}
                disabled={busy}
              >
                {t("Reload")}
              </Button>
            </p>
          )}
          {editing ? (
            <form
              className="space-y-4"
              onSubmit={(e) => {
                e.preventDefault();
                void save();
              }}
            >
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label htmlFor="term-source-language">
                    {t("Source language")}
                  </Label>
                  <SearchableSelect
                    id="term-source-language"
                    value={editing.data.source_language}
                    options={options}
                    disabled={busy}
                    onValueChange={(source_language) =>
                      change({ source_language })
                    }
                  />
                </div>
                <div>
                  <Label htmlFor="term-target-language">
                    {t("Target language")}
                  </Label>
                  <SearchableSelect
                    id="term-target-language"
                    value={editing.data.target_language}
                    options={options}
                    disabled={busy}
                    onValueChange={(target_language) =>
                      change({ target_language })
                    }
                  />
                </div>
                <div>
                  <Label htmlFor="source-term">{t("Source term")}</Label>
                  <Input
                    id="source-term"
                    required
                    maxLength={256}
                    value={editing.data.source_term}
                    disabled={busy}
                    onChange={(e) => change({ source_term: e.target.value })}
                  />
                </div>
                <div>
                  <Label htmlFor="target-term">{t("Translation")}</Label>
                  <Input
                    id="target-term"
                    required
                    maxLength={256}
                    value={editing.data.target_term}
                    disabled={busy}
                    onChange={(e) => change({ target_term: e.target.value })}
                  />
                </div>
              </div>
              <label className="flex gap-2 items-center">
                <input
                  type="checkbox"
                  checked={editing.data.forbidden ?? false}
                  disabled={busy}
                  onChange={(e) => change({ forbidden: e.target.checked })}
                />
                {t("Forbidden translation")}
              </label>
              <label className="flex gap-2 items-center">
                <input
                  type="checkbox"
                  checked={editing.data.case_sensitive ?? false}
                  disabled={busy}
                  onChange={(e) => change({ case_sensitive: e.target.checked })}
                />
                {t("Case sensitive")}
              </label>
              <div>
                <Label htmlFor="term-note">{t("Note")}</Label>
                <Input
                  id="term-note"
                  maxLength={1000}
                  value={editing.data.note ?? ""}
                  disabled={busy}
                  onChange={(e) => change({ note: e.target.value })}
                />
              </div>
              <div className="flex justify-end gap-2">
                <Button
                  type="button"
                  variant="outline"
                  disabled={busy}
                  onClick={() => {
                    if (dirty) setConfirmation("cancel");
                    else setEditing(null);
                  }}
                >
                  {t("Cancel")}
                </Button>
                <Button
                  disabled={
                    busy ||
                    !editing.data.source_language ||
                    !editing.data.target_language
                  }
                >
                  {busy ? t("Saving…") : t("Save term")}
                </Button>
              </div>
            </form>
          ) : (
            <>
              <form
                className="flex gap-2"
                onSubmit={(e) => {
                  e.preventDefault();
                  setSearch(query);
                }}
              >
                <Input
                  aria-label={t("Search terms")}
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  disabled={busy}
                  maxLength={256}
                />
                <Button variant="outline" disabled={busy}>
                  {t("Search")}
                </Button>
                {canManage && (
                  <Button
                    type="button"
                    disabled={busy}
                    onClick={() => {
                      setError(null);
                      setDirty(false);
                      setEditing({
                        id: crypto.randomUUID(),
                        data: {
                          expected_version: 0,
                          source_language:
                            languages.find((l) => l.code === "en")?.code ??
                            languages[0]?.code ??
                            "",
                          target_language:
                            languages.find((l) => l.code !== "en")?.code ?? "",
                          source_term: "",
                          target_term: "",
                          note: "",
                          forbidden: false,
                          case_sensitive: false,
                        },
                      });
                    }}
                  >
                    {t("Add term")}
                  </Button>
                )}
              </form>
              {loading ? (
                <p role="status">{t("Loading glossary…")}</p>
              ) : (
                <div className="space-y-2">
                  {!items.length && (
                    <p className="text-muted-foreground">{t("No terms")}</p>
                  )}
                  {items.map((item) => (
                    <article
                      className="rounded-md border p-3 flex gap-3 items-start"
                      key={item.id}
                    >
                      <div className="flex-1 min-w-0 break-words">
                        <p className="text-xs text-muted-foreground">
                          {item.source_language} → {item.target_language}
                        </p>
                        <p>
                          <strong>{item.source_term}</strong> →{" "}
                          <span
                            className={
                              item.forbidden
                                ? "text-destructive line-through"
                                : ""
                            }
                          >
                            {item.target_term}
                          </span>
                        </p>
                        <p className="text-xs text-muted-foreground">
                          {item.forbidden ? t("Forbidden") : t("Preferred")}
                          {item.case_sensitive ? t(" · Case sensitive") : ""}
                        </p>
                        {item.note && <p className="text-sm">{item.note}</p>}
                      </div>
                      {canManage && (
                        <>
                          <Button
                            variant="ghost"
                            size="icon"
                            aria-label={t("Edit {{v0}}", {
                              v0: item.source_term,
                            })}
                            disabled={busy}
                            onClick={() => {
                              setDirty(false);
                              const {
                                source_language,
                                target_language,
                                source_term,
                                target_term,
                                forbidden,
                                case_sensitive,
                                note,
                              } = item;
                              setEditing({
                                id: item.id,
                                data: {
                                  expected_version: item.version,
                                  source_language,
                                  target_language,
                                  source_term,
                                  target_term,
                                  forbidden,
                                  case_sensitive,
                                  note,
                                },
                              });
                            }}
                          >
                            <Pencil className="size-4" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="icon"
                            aria-label={t("Delete {{v0}}", {
                              v0: item.source_term,
                            })}
                            disabled={busy}
                            onClick={() => setConfirmation(item)}
                          >
                            <Trash2 className="size-4" />
                          </Button>
                        </>
                      )}
                    </article>
                  ))}
                  {next && (
                    <Button
                      variant="outline"
                      disabled={busy}
                      onClick={() => void loadMore()}
                    >
                      {t("Load more")}
                    </Button>
                  )}
                </div>
              )}
            </>
          )}
        </DialogContent>
      </Dialog>
      <AlertDialog
        open={!!confirmation}
        onOpenChange={(open) => {
          if (!open) setConfirmation(null);
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              {typeof confirmation === "object"
                ? t("Delete term?")
                : t("Discard changes?")}
            </AlertDialogTitle>
            <AlertDialogDescription>
              {typeof confirmation === "object"
                ? t("The term will be removed from this glossary.")
                : t("Your unsaved changes will be lost.")}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{t("Keep")}</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => {
                const action = confirmation;
                setConfirmation(null);
                if (action === "close") onClose();
                else if (action === "cancel") {
                  setEditing(null);
                  setDirty(false);
                } else if (action) void remove(action);
              }}
            >
              {typeof confirmation === "object" ? t("Delete") : t("Discard")}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
