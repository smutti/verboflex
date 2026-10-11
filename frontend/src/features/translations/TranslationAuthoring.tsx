import { useEffect, useMemo, useRef, useState } from "react";
import { Plus, Pencil, Trash2, Check } from "lucide-react";
import { toast } from "sonner";
import {
  getAuthoringDestinations,
  getAuthoringPluralForms,
  listAuthoringRequests,
  saveAuthoringRequest,
  reviewAuthoringRequest,
  discardAuthoringRequest,
  getTranslationGroup,
  type AuthoringDestination,
  type AuthoringInput,
  type AuthoringResponse,
  type TranslationKeySummary,
} from "../../api/client";
import { Button } from "../../components/ui/button";
import { Input } from "../../components/ui/input";
import { Label } from "../../components/ui/label";
import { Textarea } from "../../components/ui/textarea";
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
  AlertDialogTitle,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogCancel,
  AlertDialogAction,
} from "../../components/ui/alert-dialog";
import { countTranslationGraphemes } from "./TranslationEditor";

export type AuthoringSelection = {
  item: TranslationKeySummary;
  language: string;
} | null;
type Props = {
  accessToken: string;
  productId: string;
  canWrite: boolean;
  canReview: boolean;
  selection: AuthoringSelection;
  onClearSelection: () => void;
  onNew: (open: () => void) => void;
};
function errorMessage(error: unknown) {
  return typeof error === "object" &&
    error &&
    "detail" in error &&
    typeof error.detail === "string"
    ? error.detail
    : "Could not save. Please try again.";
}
const destinationId = (d: AuthoringDestination) =>
  `${d.scope_id}:${d.file_position}`;

export function TranslationAuthoring({
  accessToken,
  productId,
  canWrite,
  canReview,
  selection,
  onClearSelection,
  onNew,
}: Props) {
  const [page, setPage] = useState<AuthoringResponse[]>([]);
  const [next, setNext] = useState<string | null>(null);
  const [loadError, setLoadError] = useState(false);
  const [revision, setRevision] = useState(0);
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<AuthoringResponse | null>(null);
  const [deleting, setDeleting] = useState<AuthoringResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [expanded, setExpanded] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    void listAuthoringRequests({
      auth: accessToken,
      path: { product_id: productId },
      signal: controller.signal,
    })
      .then((r) => {
        if (controller.signal.aborted) return;
        if (!r.data) {
          setLoadError(true);
          return;
        }
        setPage(r.data.items);
        setNext(r.data.next_after ?? null);
        setLoadError(false);
      })
      .catch(() => {
        if (!controller.signal.aborted) setLoadError(true);
      });
    return () => controller.abort();
  }, [accessToken, productId, revision]);
  async function act(
    row: AuthoringResponse,
    state: "approved" | "rejected" | null,
  ) {
    if (busy) return;
    setBusy(true);
    try {
      const path = { product_id: productId, request_id: row.id };
      const result = state
        ? await reviewAuthoringRequest({
            auth: accessToken,
            path,
            body: { expected_version: row.version, state },
          })
        : await discardAuthoringRequest({
            auth: accessToken,
            path,
            query: { expected_version: row.version },
          });
      if (result.error) {
        toast.error(errorMessage(result.error));
        return;
      }
      setRevision((r) => r + 1);
      toast.success(
        state
          ? state === "approved"
            ? "Approved"
            : "Rejected"
          : "Draft deleted",
      );
    } catch {
      toast.error("Could not update this draft");
    } finally {
      setBusy(false);
    }
  }
  return (
    <section aria-label="New keys and translations" className="space-y-3">
      <div className="flex flex-wrap gap-2">
        {canWrite && (
          <Button
            onClick={() =>
              onNew(() => {
                setEditing(null);
                setOpen(true);
              })
            }
          >
            <Plus />
            New key
          </Button>
        )}
        {(page.length > 0 || loadError) && (
          <Button variant="outline" onClick={() => setExpanded(!expanded)}>
            New entries{" "}
            {page.length ? `(${page.length}${next ? "+" : ""})` : ""}
          </Button>
        )}
      </div>
      {expanded && (
        <div className="max-h-80 overflow-auto rounded-lg border divide-y">
          {loadError && (
            <Button variant="outline" onClick={() => setRevision((r) => r + 1)}>
              Retry new entries
            </Button>
          )}
          {page.map((row) => (
            <div key={row.id} className="flex flex-wrap items-center gap-3 p-3">
              <div className="min-w-0 grow">
                <p className="font-mono break-all">{row.input.key}</p>
                <p className="text-sm text-muted-foreground">
                  {row.input.language} · {row.state}
                  {row.source_changed ? " · Source changed" : ""}
                </p>
              </div>
              {canWrite && (
                <Button
                  variant="outline"
                  size="icon"
                  aria-label={`Edit new entry ${row.input.key} (${row.input.language})`}
                  disabled={busy}
                  onClick={() => {
                    setEditing(row);
                    setOpen(true);
                  }}
                >
                  <Pencil />
                </Button>
              )}
              {canReview && row.state !== "approved" && (
                <Button
                  variant="outline"
                  disabled={busy || row.source_changed}
                  onClick={() => void act(row, "approved")}
                >
                  <Check />
                  Approve
                </Button>
              )}
              {canReview && row.state !== "rejected" && (
                <Button
                  variant="ghost"
                  disabled={busy}
                  onClick={() => void act(row, "rejected")}
                >
                  Reject
                </Button>
              )}
              {canWrite && (
                <Button
                  variant="ghost"
                  size="icon"
                  disabled={busy}
                  aria-label={`Delete draft ${row.input.key}`}
                  onClick={() => setDeleting(row)}
                >
                  <Trash2 />
                </Button>
              )}
            </div>
          ))}
          {next && (
            <Button
              variant="ghost"
              disabled={busy}
              onClick={async () => {
                setBusy(true);
                try {
                  const r = await listAuthoringRequests({
                    auth: accessToken,
                    path: { product_id: productId },
                    query: { after: next },
                  });
                  if (r.data) {
                    setPage((p) => [...p, ...r.data!.items]);
                    setNext(r.data.next_after ?? null);
                  } else toast.error("Could not load entries");
                } catch {
                  toast.error("Could not load entries");
                } finally {
                  setBusy(false);
                }
              }}
            >
              Load more
            </Button>
          )}
        </div>
      )}
      <AlertDialog
        open={!!deleting}
        onOpenChange={(v) => {
          if (!v) setDeleting(null);
        }}
      >
        <AlertDialogContent>
          <AlertDialogTitle>Delete this draft?</AlertDialogTitle>
          <AlertDialogDescription>
            {deleting?.input.key} · {deleting?.input.language}
          </AlertDialogDescription>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => {
                if (deleting) void act(deleting, null);
              }}
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
      {(open || selection) && (
        <AuthoringDialog
          key={editing?.id ?? selection?.item.translation_key_id ?? "new"}
          accessToken={accessToken}
          productId={productId}
          editing={editing}
          selection={selection}
          onClose={() => {
            setOpen(false);
            setEditing(null);
            onClearSelection();
          }}
          onSaved={() => {
            setRevision((r) => r + 1);
            setExpanded(true);
            setOpen(false);
            setEditing(null);
            onClearSelection();
          }}
        />
      )}
    </section>
  );
}
function AuthoringDialog({
  accessToken,
  productId,
  editing,
  selection,
  onClose,
  onSaved,
}: {
  accessToken: string;
  productId: string;
  editing: AuthoringResponse | null;
  selection: AuthoringSelection;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [destinations, setDestinations] = useState<AuthoringDestination[]>([]);
  const [data, setData] = useState<AuthoringInput | null>(
    editing?.input ?? null,
  );
  const [destination, setDestination] = useState("");
  const [failure, setFailure] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [dirty, setDirty] = useState(false);
  const [invalidPath, setInvalidPath] = useState(false);
  const [confirmClose, setConfirmClose] = useState(false);
  const [knownForms, setKnownForms] = useState<
    {
      form: string;
      kind: string;
      context: string;
      identity: string;
      disambiguation: string;
    }[]
  >([]);
  const existingForms = useMemo(
    () =>
      knownForms
        .filter(
          (f) =>
            f.kind === "android_quantity" ||
            (f.identity === (data?.identity_kind ?? "id") &&
              (f.identity === "id" ||
                (f.context === data?.context &&
                  f.disambiguation === (data?.disambiguation ?? "")))),
        )
        .map((f) => f.form),
    [knownForms, data?.identity_kind, data?.context, data?.disambiguation],
  );
  const [formOptions, setFormOptions] = useState<
    { form: string; label: string }[]
  >([]);
  const requestId = useRef(editing?.id ?? crypto.randomUUID());
  const selected = destinations.find((d) => destinationId(d) === destination);
  useEffect(() => {
    const controller = new AbortController();
    void (async () => {
      const r = await getAuthoringDestinations({
        auth: accessToken,
        path: { product_id: productId },
        signal: controller.signal,
      });
      if (!r.data) throw new Error("Destinations could not be loaded");
      const all = r.data.items.filter(
        (d) =>
          !selection ||
          (d.scope_id === selection.item.scope_id &&
            d.languages.includes(selection.language)),
      );
      let next = editing?.input;
      let currentForms: typeof knownForms = [];
      if (selection) {
        const groupId =
          selection.item.slots.find(
            (s) => s.group_id && s.language === selection.item.base_language,
          )?.group_id ?? selection.item.slots.find((s) => s.group_id)?.group_id;
        if (!groupId) throw new Error("Source context unavailable");
        const detail = await getTranslationGroup({
          auth: accessToken,
          path: { translation_group_id: groupId },
          signal: controller.signal,
        });
        if (
          !detail.data ||
          detail.data.id !== groupId ||
          detail.data.product_id !== selection.item.product_id
        )
          throw new Error("Source context unavailable");
        const first = detail.data.values[0];
        const fields = Object.fromEntries(
          (first?.selector_fields ?? []).map((f) => [f.name, f.value]),
        );
        const targetSlot = selection.item.slots.find(
          (s) => s.language === selection.language,
        );
        if (targetSlot?.group_id) {
          const targetDetail = await getTranslationGroup({
            auth: accessToken,
            path: { translation_group_id: targetSlot.group_id },
            signal: controller.signal,
          });
          if (!targetDetail.data) throw new Error("Plural context unavailable");
          currentForms = targetDetail.data.values.flatMap((v) => {
            const field = v.selector_fields?.find(
              (f) => f.name === "quantity" || f.name === "form_index",
            );
            const get = (name: string) =>
              String(
                v.selector_fields?.find((f) => f.name === name)?.value ?? "",
              );
            return field
              ? [
                  {
                    form: String(field.value),
                    kind: v.selector_kind,
                    context: get("context"),
                    identity: get("identity_kind"),
                    disambiguation: get("disambiguation"),
                  },
                ]
              : [];
          });
        }
        const target = all.length === 1 ? all[0] : null;
        next = {
          scope_id: selection.item.scope_id,
          execution_id: target?.execution_id ?? "",
          file_position: target?.file_position ?? 0,
          parent_key_id: selection.item.translation_key_id,
          key: detail.data.raw_key,
          language: selection.language,
          kind:
            first?.selector_kind === "qt_numerus" ||
            first?.selector_kind === "android_quantity"
              ? "plural"
              : "text",
          source_text:
            first?.source_text ??
            detail.data.source_context?.[0]?.source_text ??
            "",
          context: typeof fields.context === "string" ? fields.context : "",
          identity_kind: fields.identity_kind === "source" ? "source" : "id",
          disambiguation:
            typeof fields.disambiguation === "string"
              ? fields.disambiguation
              : "",
          parents: Array.isArray(fields.parents)
            ? fields.parents.map(String)
            : [],
          forms: [{ form: "other", text: "" }],
        };
      }
      if (controller.signal.aborted) return;
      setDestinations(all);
      setKnownForms(currentForms);
      const initial = editing
        ? all.find(
            (d) =>
              d.scope_id === editing.input.scope_id && d.path === editing.path,
          )
        : all.length === 1
          ? all[0]
          : null;
      if (initial) setDestination(destinationId(initial));
      setData(
        next ?? {
          scope_id: initial?.scope_id ?? "",
          execution_id: initial?.execution_id ?? "",
          file_position: initial?.file_position ?? 0,
          key: "",
          language: initial?.languages[0] ?? "",
          kind: "text",
          forms: [{ form: "other", text: "" }],
        },
      );
      setLoading(false);
    })().catch((error) => {
      if (!controller.signal.aborted) {
        setFailure(
          error instanceof Error
            ? error.message
            : "Could not load destinations",
        );
        setLoading(false);
      }
    });
    return () => controller.abort();
  }, [accessToken, productId, editing, selection]);
  useEffect(() => {
    if (!selected || !data?.language || data.kind !== "plural") return;
    const controller = new AbortController();
    void getAuthoringPluralForms({
      auth: accessToken,
      path: { product_id: productId },
      query: { format: selected.format, language: data.language },
      signal: controller.signal,
    })
      .then((r) => {
        if (controller.signal.aborted) return;
        if (!r.data) {
          setFailure(errorMessage(r.error));
          return;
        }
        setFormOptions(
          r.data.forms.filter((f) => !existingForms.includes(f.form)),
        );
        setData((current) =>
          current
            ? {
                ...current,
                forms: r
                  .data!.forms.filter((f) => !existingForms.includes(f.form))
                  .map((f) => ({
                    form: f.form,
                    text:
                      current.forms.find((v) => v.form === f.form)?.text ?? "",
                  })),
              }
            : current,
        );
      })
      .catch(() => {
        if (!controller.signal.aborted)
          setFailure("Could not load plural forms");
      });
    return () => controller.abort();
  }, [
    accessToken,
    productId,
    selected,
    data?.language,
    data?.kind,
    existingForms,
  ]);
  useEffect(() => {
    if (!dirty) return;
    const warn = (event: BeforeUnloadEvent) => event.preventDefault();
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty]);
  function change(patch: Partial<AuthoringInput>) {
    setData((d) => (d ? { ...d, ...patch } : d));
    setDirty(true);
    setFailure(null);
  }
  function close() {
    if (busy) return;
    if (dirty) setConfirmClose(true);
    else onClose();
  }
  async function save() {
    if (!data || !selected || busy || invalidPath) return;
    setBusy(true);
    setFailure(null);
    try {
      const result = await saveAuthoringRequest({
        auth: accessToken,
        path: { product_id: productId, request_id: requestId.current },
        body: {
          ...data,
          scope_id: selected.scope_id,
          execution_id: selected.execution_id,
          file_position: selected.file_position,
          expected_version: editing?.version ?? 0,
        },
      });
      if (!result.data) {
        setFailure(errorMessage(result.error));
        return;
      }
      setDirty(false);
      toast.success("Draft saved");
      onSaved();
    } catch {
      setFailure("Could not save. Please try again.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <Dialog
        open
        onOpenChange={(v) => {
          if (!v) close();
        }}
      >
        <DialogContent className="sm:max-w-2xl max-h-[90vh] overflow-y-auto">
          <DialogTitle>
            {editing
              ? "Edit new entry"
              : selection
                ? "Add translation"
                : "New key"}
          </DialogTitle>
          <DialogDescription className="sr-only">
            Create a translation draft for review.
          </DialogDescription>
          {loading && <p role="status">Loading destinations…</p>}
          {failure && (
            <p role="alert" className="text-destructive">
              {failure}
            </p>
          )}
          {data && !loading && (
            <form
              className="space-y-4"
              onSubmit={(e) => {
                e.preventDefault();
                void save();
              }}
            >
              <div className="space-y-1">
                <Label htmlFor="authoring-file">File</Label>
                <SearchableSelect
                  id="authoring-file"
                  value={destination}
                  options={destinations.map((d) => ({
                    value: destinationId(d),
                    label: `${d.repository} · ${d.path}`,
                  }))}
                  disabled={busy}
                  onValueChange={(value) => {
                    const d = destinations.find(
                      (v) => destinationId(v) === value,
                    )!;
                    setDestination(value);
                    change({
                      ...(d.format !== selected?.format ||
                      !d.languages.includes(data.language)
                        ? { forms: [{ form: "other", text: "" }] }
                        : {}),
                      language: d.languages.includes(data.language)
                        ? data.language
                        : (d.languages[0] ?? ""),
                      kind: ["android_xml", "qt_ts"].includes(d.format)
                        ? data.kind
                        : "text",
                      ...(!["android_xml", "qt_ts"].includes(d.format) &&
                      data.kind === "plural"
                        ? { forms: [{ text: "" }] }
                        : {}),
                    });
                  }}
                />
              </div>
              {destinations.length === 0 && (
                <p>No mapped file is available for this language.</p>
              )}
              {selected?.provider === "github" && (
                <p className="text-sm text-muted-foreground">
                  GitHub drafts stay local. Remote submission is not available.
                </p>
              )}
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <Label htmlFor="authoring-language">Language</Label>
                  <SearchableSelect
                    id="authoring-language"
                    value={data.language}
                    options={(selected?.languages ?? []).map((v) => ({
                      value: v,
                      label: v,
                    }))}
                    disabled={busy || !!selection || !!editing}
                    onValueChange={(language) =>
                      change({ language, forms: [{ form: "other", text: "" }] })
                    }
                  />
                </div>
                <div className="space-y-1">
                  <Label htmlFor="authoring-type">Type</Label>
                  <SearchableSelect
                    id="authoring-type"
                    value={data.kind ?? "text"}
                    disabled={busy || !!selection || !!editing}
                    options={[
                      { value: "text", label: "Text" },
                      ...(["android_xml", "qt_ts"].includes(
                        selected?.format ?? "",
                      )
                        ? [{ value: "plural", label: "Plural" }]
                        : []),
                    ]}
                    onValueChange={(kind) => {
                      setFormOptions([]);
                      change({
                        kind: kind as "text" | "plural",
                        forms: [{ form: "other", text: "" }],
                      });
                    }}
                  />
                </div>
              </div>
              <div className="space-y-1">
                <Label htmlFor="authoring-key">Key</Label>
                <Input
                  id="authoring-key"
                  required
                  maxLength={4096}
                  disabled={busy || !!selection || !!editing}
                  value={data.key}
                  onChange={(e) =>
                    change({
                      key: e.target.value,
                      ...(data.identity_kind === "source"
                        ? { source_text: e.target.value }
                        : {}),
                    })
                  }
                />
              </div>
              {selected?.format === "qt_ts" && (
                <>
                  <div className="space-y-1">
                    <Label htmlFor="authoring-identity">Key type</Label>
                    <SearchableSelect
                      id="authoring-identity"
                      value={data.identity_kind ?? "id"}
                      disabled={busy || !!selection || !!editing}
                      options={[
                        { value: "id", label: "Message ID" },
                        { value: "source", label: "Source text" },
                      ]}
                      onValueChange={(identity_kind) =>
                        change({
                          identity_kind: identity_kind as "id" | "source",
                          ...(identity_kind === "source"
                            ? { source_text: data.key }
                            : {}),
                        })
                      }
                    />
                  </div>
                  <div className="space-y-1">
                    <Label htmlFor="authoring-context">Context</Label>
                    <Input
                      id="authoring-context"
                      required
                      value={data.context ?? ""}
                      disabled={busy || !!editing}
                      onChange={(e) => change({ context: e.target.value })}
                    />
                  </div>
                  <div className="space-y-1">
                    <Label htmlFor="authoring-source">Source text</Label>
                    <Textarea
                      id="authoring-source"
                      required
                      value={data.source_text ?? ""}
                      disabled={
                        busy || data.identity_kind === "source" || !!selection
                      }
                      onChange={(e) => change({ source_text: e.target.value })}
                    />
                  </div>
                </>
              )}
              {selected?.format === "json" && (
                <div className="space-y-1">
                  <Label htmlFor="authoring-parents">
                    Parent path (JSON array)
                  </Label>
                  <Input
                    id="authoring-parents"
                    defaultValue={JSON.stringify(data.parents ?? [])}
                    disabled={busy || !!selection || !!editing}
                    onBlur={(e) => {
                      try {
                        const parents: unknown = JSON.parse(e.target.value);
                        if (
                          !Array.isArray(parents) ||
                          !parents.every((v) => typeof v === "string")
                        )
                          throw new Error();
                        setInvalidPath(false);
                        change({ parents });
                      } catch {
                        setFailure(
                          'Enter a path such as ["screen", "buttons"]',
                        );
                      }
                    }}
                  />
                </div>
              )}
              {data.forms.length === 0 && (
                <p>All plural forms are already present.</p>
              )}
              {data.forms.map((form, index) => {
                const count = countTranslationGraphemes(form.text);
                const over = data.max_chars != null && count > data.max_chars;
                return (
                  <div className="space-y-1" key={form.form}>
                    <Label htmlFor={`authoring-form-${form.form}`}>
                      {data.kind === "plural"
                        ? (formOptions.find((f) => f.form === form.form)
                            ?.label ?? form.form)
                        : "Translation"}
                    </Label>
                    <Textarea
                      id={`authoring-form-${form.form}`}
                      lang={data.language}
                      dir="auto"
                      disabled={busy}
                      maxLength={65536}
                      value={form.text}
                      aria-invalid={over}
                      className={
                        over
                          ? "border-destructive bg-red-50"
                          : "border-blue-300 bg-blue-50/40"
                      }
                      onChange={(e) =>
                        change({
                          forms: data.forms.map((f, i) =>
                            i === index ? { ...f, text: e.target.value } : f,
                          ),
                        })
                      }
                    />
                    <p
                      className={`text-sm ${over ? "font-semibold text-destructive" : "text-muted-foreground"}`}
                    >
                      {count}
                      {data.max_chars != null ? ` / ${data.max_chars}` : ""}
                      {over ? " · Over limit" : ""}
                    </p>
                  </div>
                );
              })}
              <div className="space-y-1">
                <Label htmlFor="authoring-max">Character limit</Label>
                <Input
                  id="authoring-max"
                  type="number"
                  min={0}
                  max={1048576}
                  disabled={busy}
                  value={data.max_chars ?? ""}
                  onChange={(e) =>
                    change({
                      max_chars:
                        e.target.value === "" ? null : Number(e.target.value),
                    })
                  }
                />
              </div>
              <div className="flex justify-end gap-2">
                <Button
                  type="button"
                  variant="outline"
                  disabled={busy}
                  onClick={close}
                >
                  Cancel
                </Button>
                <Button
                  type="submit"
                  disabled={
                    busy ||
                    !selected ||
                    !data.key ||
                    !data.language ||
                    data.forms.length === 0 ||
                    invalidPath
                  }
                >
                  {busy ? "Saving…" : "Save"}
                </Button>
              </div>
            </form>
          )}
        </DialogContent>
      </Dialog>
      <AlertDialog open={confirmClose} onOpenChange={setConfirmClose}>
        <AlertDialogContent>
          <AlertDialogTitle>Discard unsaved changes?</AlertDialogTitle>
          <AlertDialogDescription>
            Your changes have not been saved.
          </AlertDialogDescription>
          <AlertDialogFooter>
            <AlertDialogCancel>Keep editing</AlertDialogCancel>
            <AlertDialogAction onClick={onClose}>Discard</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
