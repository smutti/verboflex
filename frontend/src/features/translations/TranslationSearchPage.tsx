import { CodeKeyCatalog } from "./CodeKeyCatalog";
import { rolesForProduct } from "../auth/productRoles";
import { Glossary } from "./Glossary";
import {
  TranslationAuthoring,
  type AuthoringSelection,
} from "./TranslationAuthoring";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  useLocation,
  useOutletContext,
  useSearchParams,
} from "react-router-dom";
import {
  getTranslationGroup,
  listTranslationOptions,
  type TranslationKeySummary,
  type TranslationGroupDetailResponse,
  type TranslationProposalConflictResponse,
  type TranslationProposalResponse,
  type TranslationOptionsResponse,
} from "../../api/client";
import { Alert, AlertDescription, AlertTitle } from "../../components/ui/alert";
import { Button } from "../../components/ui/button";
import { Input } from "../../components/ui/input";
import { Label } from "../../components/ui/label";
import { Skeleton } from "../../components/ui/skeleton";
import { TranslationFilters } from "./TranslationFilters";
import { translationFilterLabels } from "./translationFilterLabels";
import {
  TranslationResultList,
  type TranslationContextSelection,
} from "./TranslationResultList";
import {
  loadTranslationPreferences,
  sanitizeTranslationPreferences,
  saveTranslationPreferences,
  coherentTranslationSelection,
} from "./translationPreferences";
import {
  useTranslationSearch,
  translationSearchIdentity,
  type TranslationSearchFilters,
  type TranslationSearchSnapshot,
} from "./useTranslationSearch";
import type { TranslationsWorkspaceContext } from "./TranslationsWorkspace";
import {
  createActiveTranslationDraft,
  writableTranslationDetail,
  type ActiveTranslationDraft,
  TranslationEditor,
} from "./TranslationEditor";
import { completeTranslationDetail } from "./translationDetailAuthority";
import { TranslationConflictDialog } from "./TranslationConflictDialog";
import { TranslationContextPanel } from "./TranslationContextPanel";
import type { DiscussionDraftState } from "./Discussion";
import { Dialog as SheetPrimitive } from "radix-ui";
import {
  Sheet,
  SheetTitle,
  SheetDescription,
  SheetClose,
} from "../../components/ui/sheet";
import {
  AlertDialog,
  AlertDialogContent,
  AlertDialogTitle,
  AlertDialogDescription,
  AlertDialogHeader,
  AlertDialogFooter,
  AlertDialogCancel,
  AlertDialogAction,
} from "../../components/ui/alert-dialog";

const DEFAULT_FILTERS: TranslationSearchFilters = {
  productId: null,
  language: null,
  state: null,
  violation: null,
  deleted: "active",
};
const EMPTY_OPTIONS: TranslationOptionsResponse = {
  products: [],
  languages: [],
};
type Seed = {
  query: string;
  filters: TranslationSearchFilters;
  snapshot?: TranslationSearchSnapshot | null;
  focusControl?: string;
  focusLanguage?: string | null;
};
type ReadyOptions = { options: TranslationOptionsResponse; seed: Seed };
type LocatedSnapshot = TranslationSearchSnapshot & {
  searchLocationKey?: string;
};

function LoadingResults() {
  return (
    <div className="space-y-(--space-md)" role="status" aria-live="polite">
      <span>Loading translations</span>
      {Array.from({ length: 5 }, (_, index) => (
        <div
          key={index}
          data-translation-skeleton
          className="grid grid-cols-1 gap-(--space-md) border-b p-(--space-md) md:grid-cols-6"
          aria-hidden="true"
        >
          {Array.from({ length: 6 }, (_, column) => (
            <Skeleton key={column} className="h-12 w-full" />
          ))}
        </div>
      ))}
    </div>
  );
}

function SearchError({
  onRetry,
  alertRef,
}: {
  onRetry: () => void;
  alertRef?: React.Ref<HTMLDivElement>;
}) {
  return (
    <Alert ref={alertRef} tabIndex={-1}>
      <AlertTitle>Translations could not be loaded</AlertTitle>
      <AlertDescription className="space-y-(--space-md)">
        <Button
          type="button"
          variant="outline"
          className="min-h-[44px] min-w-[44px]"
          onClick={onRetry}
        >
          Retry search
        </Button>
      </AlertDescription>
    </Alert>
  );
}

function ResolvedSearch({
  ready,
  context,
  onRestart,
}: {
  ready: ReadyOptions;
  context: TranslationsWorkspaceContext;
  onRestart: (seed: Seed) => void;
}) {
  const { options, seed } = ready;
  const [authoringSelection, setAuthoringSelection] =
    useState<AuthoringSelection>(null);
  const lockedProduct = context.lockedProduct;
  const search = useTranslationSearch({
    accessToken: context.accessToken,
    initialQuery: seed.query,
    initialFilters: seed.filters,
    initialSnapshot: seed.snapshot,
  });
  const refreshSearch = search.refresh;
  const awaitingTarget = search.items.some((item) =>
    item.slots.some(
      (slot) =>
        slot.pending_change?.state === "approved" &&
        slot.pending_change.target_branch &&
        !slot.pending_change.target_integrated,
    ),
  );
  useEffect(() => {
    if (!awaitingTarget || context.activeDraft || search.items.length > 50)
      return;
    const timer = window.setInterval(() => {
      if (document.visibilityState === "visible") refreshSearch();
    }, 30_000);
    return () => window.clearInterval(timer);
  }, [awaitingTarget, context.activeDraft, search.items.length, refreshSearch]);
  useEffect(() => {
    if (
      search.filters.viewMode !== "bilingual" ||
      search.isInitialLoading ||
      search.initialError
    )
      return;
    const next = coherentTranslationSelection(
      { ...search.filters, visibleLanguages: [...search.visibleLanguages] },
      search.availableLanguages.map(({ code }) => code),
      search.visibleLanguages,
      [
        ...new Set(
          search.items.flatMap((item) =>
            item.base_language ? [item.base_language] : [],
          ),
        ),
      ],
    );
    if (
      next.language !== search.filters.language ||
      JSON.stringify(next.visibleLanguages) !==
        JSON.stringify([...search.visibleLanguages].sort())
    ) {
      search.setFilters(next);
    }
  }, [search]);
  const resultHeading = useRef<HTMLHeadingElement>(null);
  const resultRegion = useRef<HTMLElement>(null);
  const alertRef = useRef<HTMLDivElement>(null);
  const explicitAction = useRef(false);
  const previousIdentity = useRef(search.requestIdentity);
  const restorationDone = useRef(false);
  const { setSnapshot: saveSnapshot } = context;
  const searchLocationKey = useLocation().key;
  const snapshotDirty = useRef(false);
  const setSnapshot = useCallback(
    (snapshot: TranslationSearchSnapshot) => {
      const located: LocatedSnapshot = {
        ...snapshot,
        ...(snapshotDirty.current ? { invalidated: true } : {}),
        searchLocationKey,
      };
      saveSnapshot(located);
    },
    [saveSnapshot, searchLocationKey],
  );
  const [conflict, setConflict] = useState<{
    draft: ActiveTranslationDraft;
    response: TranslationProposalConflictResponse;
  } | null>(null);
  const [proposalOverrides, setProposalOverrides] = useState<
    ReadonlyMap<string, TranslationProposalResponse>
  >(() => new Map());
  const [editorLoad, setEditorLoad] = useState<{
    groupId: string;
    status: "loading" | "error";
  } | null>(null);
  const [retainedItem, setRetainedItem] =
    useState<TranslationKeySummary | null>(null);
  const [queueMessage, setQueueMessage] = useState<string | null>(null);
  const editorTrigger = useRef<HTMLElement | null>(null);
  const savedEditorFocus = useRef<string | null>(null);
  useEffect(() => {
    if (!savedEditorFocus.current) return;
    const button = Array.from(
      document.querySelectorAll<HTMLButtonElement>(
        "[data-translation-editor-trigger]",
      ),
    ).find(
      (element) =>
        element.dataset.translationEditorTrigger === savedEditorFocus.current,
    );
    if (button) {
      button.focus({ preventScroll: true });
      savedEditorFocus.current = null;
    }
  }, [context.activeDraft, search.items, retainedItem]);
  const [editorReturnFocusTo, setEditorReturnFocusTo] =
    useState<HTMLElement | null>(null);
  const editorGeneration = useRef(0);
  const editorController = useRef<AbortController | null>(null);
  useEffect(
    () => () => {
      editorController.current?.abort();
    },
    [],
  );

  const [selectedContext, setSelectedContext] =
    useState<TranslationContextSelection | null>(null);
  const [contextOpen, setContextOpen] = useState(false);
  const [contextLoad, setContextLoad] = useState<{
    selection: TranslationContextSelection;
    detail?: TranslationGroupDetailResponse;
    failed?: boolean;
  } | null>(null);
  const contextController = useRef<AbortController | null>(null);
  const contextGeneration = useRef(0);
  const contextContent = useRef<HTMLDivElement | null>(null);
  const [discussionState, setDiscussionState] = useState<DiscussionDraftState>({
    dirty: false,
    submitting: false,
  });
  const previousDiscussionState = useRef<DiscussionDraftState>({
    dirty: false,
    submitting: false,
  });
  const trackDiscussion = useCallback((state: DiscussionDraftState) => {
    setDiscussionState((current) =>
      current.dirty === state.dirty && current.submitting === state.submitting
        ? current
        : state,
    );
  }, []);
  useEffect(() => {
    const previous = previousDiscussionState.current;
    previousDiscussionState.current = discussionState;
    if (
      previous.submitting &&
      !discussionState.submitting &&
      !discussionState.dirty &&
      selectedContext
    ) {
      snapshotDirty.current = true;
      refreshSearch();
    }
  }, [discussionState, selectedContext, refreshSearch]);
  const [pendingReplacement, setPendingReplacement] = useState<{
    action: () => void;
    trigger: HTMLElement | null;
  } | null>(null);
  const replacementFocus = useRef<HTMLElement | null>(null);
  useEffect(() => () => contextController.current?.abort(), []);
  useEffect(() => {
    if (contextOpen)
      queueMicrotask(() =>
        contextContent.current?.focus({ preventScroll: true }),
      );
  }, [contextOpen]);

  const runWorkspaceAction = useCallback(
    (
      action: () => void,
      trigger: HTMLElement | null = null,
      replaceDiscussion = true,
    ) => {
      const accepted = () => {
        if (replaceDiscussion) {
          contextController.current?.abort();
          setSelectedContext(null);
          setContextLoad(null);
          setContextOpen(false);
          setDiscussionState({ dirty: false, submitting: false });
        }
        action();
      };
      if (replaceDiscussion && discussionState.submitting) {
        setQueueMessage(
          "Wait for the comment to finish saving before changing context.",
        );
        return;
      }
      if (replaceDiscussion && discussionState.dirty) {
        setPendingReplacement({ action: accepted, trigger });
        return;
      }
      context.runDraftGuardedAction(accepted, trigger);
    },
    [context, discussionState],
  );

  const fetchContext = useCallback(
    (selection: TranslationContextSelection) => {
      contextController.current?.abort();
      const generation = ++contextGeneration.current;
      setContextLoad((current) =>
        current?.detail && current.selection.groupId === selection.groupId
          ? { ...current, selection, failed: false }
          : { selection },
      );
      if (!selection.groupId) return;
      const controller = new AbortController();
      contextController.current = controller;
      void getTranslationGroup({
        auth: context.accessToken,
        path: { translation_group_id: selection.groupId },
        signal: controller.signal,
      })
        .then((result) => {
          if (
            controller.signal.aborted ||
            generation !== contextGeneration.current
          )
            return;
          if (
            !result.data ||
            !completeTranslationDetail(result.data, selection.groupId!) ||
            result.data.product_id !== selection.item.product_id ||
            result.data.language !== selection.language
          )
            throw new Error("Context unavailable");
          setContextLoad({ selection, detail: result.data });
        })
        .catch(() => {
          if (!controller.signal.aborted)
            setContextLoad((current) => ({
              ...current,
              selection,
              failed: true,
            }));
        });
    },
    [context.accessToken],
  );
  const openContext = (selection: TranslationContextSelection) => {
    if (
      selectedContext?.item.translation_key_id ===
        selection.item.translation_key_id &&
      selectedContext.item.scope_id === selection.item.scope_id &&
      selectedContext.language === selection.language &&
      selectedContext.groupId === selection.groupId
    ) {
      // Preserve the one mounted composer on close/reopen and tab changes.
      setSelectedContext({
        ...selectedContext,
        section: selection.section,
        trigger: selection.trigger,
      });
      setContextOpen(true);
      if (!contextOpen) fetchContext(selection);
      return;
    }
    if (
      !selectedContext &&
      context.activeDraft?.translationGroupId === selection.groupId
    ) {
      setSelectedContext(selection);
      setContextOpen(true);
      fetchContext(selection);
      return;
    }
    runWorkspaceAction(() => {
      setSelectedContext(selection);
      setContextOpen(true);
      fetchContext(selection);
    }, selection.trigger);
  };
  const closeContext = () => {
    setContextOpen(false);
    queueMicrotask(() => {
      const original = selectedContext?.trigger;
      if (original?.isConnected) {
        original.focus({ preventScroll: true });
        return;
      }
      // A fresh key page can replace the invoking button while discussion stays mounted.
      const label = original
        ?.getAttribute("aria-label")
        ?.replace(/, [\d,]+ comments$/, "");
      const keyId =
        selectedContext &&
        `${selectedContext.item.product_id}:${selectedContext.item.scope_id}:${selectedContext.item.translation_key_id}`;
      const key = Array.from(
        document.querySelectorAll<HTMLElement>("[data-translation-key-id]"),
      ).find((element) => element.dataset.translationKeyId === keyId);
      const row = Array.from(
        key?.querySelectorAll<HTMLElement>("[data-language]") ?? [],
      ).find(
        (element) => element.dataset.language === selectedContext?.language,
      );
      const replacement = Array.from(
        row?.querySelectorAll<HTMLButtonElement>("button[aria-label]") ?? [],
      ).find(
        (button) =>
          label && button.getAttribute("aria-label")?.startsWith(label),
      );
      (replacement ?? resultHeading.current)?.focus({ preventScroll: true });
    });
  };

  const openEditor = useCallback(
    (groupId: string, trigger: HTMLElement) => {
      const key =
        search.items.find((item) =>
          item.slots.some((slot) => slot.group_id === groupId),
        ) ?? retainedItem;
      const slot = key?.slots.find((slot) => slot.group_id === groupId);
      if (
        !key ||
        !slot?.editable ||
        slot.is_deleted ||
        !rolesForProduct(context.principal, key.product_id).some((role) =>
          ["admin", "translator", "product_manager_reviewer"].includes(role),
        )
      )
        return;
      runWorkspaceAction(
        () => {
          setQueueMessage(null);
          savedEditorFocus.current = null;
          editorController.current?.abort();
          const controller = new AbortController();
          const generation = ++editorGeneration.current;
          const initialContextGeneration = contextGeneration.current;
          editorController.current = controller;
          editorTrigger.current = trigger;
          setEditorReturnFocusTo(trigger);
          setEditorLoad({ groupId, status: "loading" });
          void getTranslationGroup({
            auth: context.accessToken,
            path: { translation_group_id: groupId },
            signal: controller.signal,
          })
            .then((result) => {
              if (
                controller.signal.aborted ||
                generation !== editorGeneration.current ||
                !result.data ||
                !completeTranslationDetail(result.data, groupId) ||
                result.data.is_deleted ||
                !result.data.mutation_eligible ||
                result.data.product_id !== key.product_id ||
                result.data.language !== slot.language ||
                !writableTranslationDetail(result.data, slot.edit_field)
              )
                throw new Error("Translation unavailable");
              context.setActiveDraft(
                createActiveTranslationDraft(result.data, context.principal.id),
              );
              const detail = result.data;
              if (initialContextGeneration === contextGeneration.current) {
                setContextLoad((loaded) =>
                  loaded?.selection.groupId === groupId
                    ? { selection: loaded.selection, detail }
                    : loaded,
                );
              }
              setRetainedItem(key);
              setEditorLoad(null);
            })
            .catch(() => {
              if (
                !controller.signal.aborted &&
                generation === editorGeneration.current
              )
                setEditorLoad({ groupId, status: "error" });
            });
        },
        trigger,
        false,
      );
    },
    [context, search.items, retainedItem, runWorkspaceAction],
  );
  const resetEditor = () => {
    savedEditorFocus.current = null;
    editorController.current?.abort();
    editorGeneration.current += 1;
    setEditorLoad(null);
    context.setActiveDraft(null);
    setRetainedItem(null);
    setQueueMessage(null);
  };
  const { createSnapshot, query, filters, items, nextCursor, requestIdentity } =
    search;
  useEffect(() => {
    setSnapshot(createSnapshot(window.scrollY, null));
  }, [
    setSnapshot,
    createSnapshot,
    query,
    filters,
    items,
    nextCursor,
    requestIdentity,
  ]);

  useEffect(() => {
    try {
      saveTranslationPreferences(
        localStorage,
        context.principal.id,
        options,
        search.filters,
        lockedProduct?.id,
      );
    } catch {
      /* Storage can be disabled; search stays usable in memory. */
    }
  }, [context.principal.id, lockedProduct, options, search.filters]);

  useEffect(() => {
    if (
      search.requestIdentity &&
      previousIdentity.current !== search.requestIdentity
    ) {
      previousIdentity.current = search.requestIdentity;
      resultHeading.current?.scrollIntoView({
        behavior: "instant",
        block: "start",
      });
    }
  }, [search.requestIdentity]);

  useEffect(() => {
    let active = true;
    if (search.initialError && explicitAction.current)
      queueMicrotask(() => {
        if (active) alertRef.current?.focus();
      });
    return () => {
      active = false;
    };
  }, [search.initialError]);

  useEffect(() => {
    if (seed.focusControl) {
      if (seed.focusControl === "query") {
        document
          .getElementById("translation-query")
          ?.focus({ preventScroll: true });
        return;
      }
      if (seed.focusControl === "clear") {
        document
          .querySelector<HTMLButtonElement>("[data-clear-translation-filters]")
          ?.focus({ preventScroll: true });
        return;
      }
      const control = Array.from(
        document.querySelectorAll<HTMLElement>('[role="combobox"]'),
      ).find((element) => element.id.endsWith(`-${seed.focusControl}`));
      control?.focus({ preventScroll: true });
    }
  }, [seed.focusControl]);

  useEffect(() => {
    const navigation = search.restoredNavigation;
    if (!navigation || restorationDone.current || search.isInitialLoading)
      return;
    window.scrollTo({ top: navigation.scrollAnchor, behavior: "instant" });
    const restoreFocus = () => {
      if (!navigation.focusedGroupId) {
        restorationDone.current = true;
        return true;
      }
      const link = Array.from(
        resultRegion.current?.querySelectorAll<HTMLAnchorElement>(
          "a[data-translation-group-id]",
        ) ?? [],
      ).find(
        (element) =>
          element.dataset.translationGroupId === navigation.focusedGroupId,
      );
      if (!link) return false;
      link.focus({ preventScroll: true });
      restorationDone.current = true;
      return true;
    };
    if (restoreFocus()) return;
    const observer = new MutationObserver(() => {
      if (restoreFocus()) observer.disconnect();
    });
    if (resultRegion.current)
      observer.observe(resultRegion.current, {
        childList: true,
        subtree: true,
      });
    return () => observer.disconnect();
  }, [search.restoredNavigation, search.isInitialLoading]);

  const clearAll = () => {
    runWorkspaceAction(() => {
      context.setSnapshot(null);
      onRestart({
        query: "",
        filters: {
          ...DEFAULT_FILTERS,
          productId: lockedProduct?.id ?? null,
          visibleLanguages: search.filters.visibleLanguages,
          viewMode: "multilingual",
        },
        focusControl: "clear",
      });
    }, document.querySelector("[data-clear-translation-filters]"));
  };
  const changeFilters = (filters: TranslationSearchFilters) => {
    runWorkspaceAction(
      () => {
        resetEditor();
        explicitAction.current = true;
        const nextFilters = lockedProduct
          ? { ...filters, productId: lockedProduct.id }
          : filters;
        if (nextFilters.productId !== search.filters.productId) {
          onRestart({
            query: search.query,
            filters: nextFilters,
            focusControl: "productId",
          });
        } else search.setFilters(nextFilters);
      },
      document.activeElement instanceof HTMLElement
        ? document.activeElement
        : null,
    );
  };
  const visibleItems =
    retainedItem &&
    !search.items.some(
      (item) =>
        item.translation_key_id === retainedItem.translation_key_id &&
        item.scope_id === retainedItem.scope_id,
    )
      ? [retainedItem, ...search.items]
      : search.items;
  const presentedItems = visibleItems.map((item): TranslationKeySummary => ({
    ...item,
    slots: item.slots.map((slot) => {
      const proposal = slot.group_id
        ? proposalOverrides.get(slot.group_id)
        : null;
      if (!proposal || proposal.version <= (slot.pending_change?.version ?? 0))
        return slot;
      return {
        ...slot,
        effective_text:
          proposal.state === "rejected"
            ? ((context.activeDraft?.translationGroupId === slot.group_id
                ? context.activeDraft.values[0]?.publishedText
                : contextLoad?.detail?.id === slot.group_id
                  ? contextLoad.detail.values[0]?.display_text
                  : slot.effective_text) ?? slot.effective_text)
            : (proposal.pending[0]?.text ?? slot.effective_text),
        effective_over_limit_count:
          proposal.state !== "rejected" && !proposal.reconciliation_required
            ? proposal.pending.filter((value) => value.is_over_limit).length
            : slot.over_limit_count,
        pending_change: {
          state: proposal.state,
          target_branch: proposal.target_branch,
          target_integrated: proposal.target_integrated,
          version: proposal.version,
          value_count: proposal.pending.length,
          reconciliation_required: proposal.reconciliation_required,
        },
      };
    }),
  }));
  const filtered =
    search.query !== "" ||
    (!lockedProduct && search.filters.productId !== null) ||
    search.filters.language !== null ||
    search.filters.state != null ||
    search.filters.workStatus != null ||
    search.filters.violation != null ||
    search.filters.deleted !== "active";
  const criteria = [
    search.query && `Search: ${search.query}`,
    !lockedProduct &&
      search.filters.productId &&
      `Product: ${options.products.find((item) => item.id === search.filters.productId)?.name}`,
    search.filters.language && `Language: ${search.filters.language}`,
    search.filters.workStatus &&
      `Work queue: ${translationFilterLabels.workStatus[search.filters.workStatus]}`,
    search.filters.state &&
      `Approval state: ${translationFilterLabels.state[search.filters.state]}`,
    search.filters.violation &&
      `Length status: ${translationFilterLabels.violation[search.filters.violation]}`,
    search.filters.deleted !== "active" &&
      `Deleted status: ${translationFilterLabels.deleted[search.filters.deleted]}`,
  ]
    .filter(Boolean)
    .join("; ");

  return (
    <>
      {conflict?.response.latest && (
        <TranslationConflictDialog
          open
          draft={conflict.draft}
          latest={conflict.response.latest}
          onKeepEditing={() => setConflict(null)}
          onReconcile={(draft) => {
            context.setActiveDraft(draft);
            setConflict(null);
          }}
        />
      )}
      <div className="flex flex-wrap items-start gap-2">
        {search.filters.productId && (
          <CodeKeyCatalog
            key={`catalog:${search.filters.productId}`}
            accessToken={context.accessToken}
            productId={search.filters.productId}
          />
        )}
        {(authoringSelection?.item.product_id ?? search.filters.productId) && (
          <TranslationAuthoring
            key={`authoring:${authoringSelection?.item.product_id ?? search.filters.productId}`}
            productId={
              (authoringSelection?.item.product_id ?? search.filters.productId)!
            }
            accessToken={context.accessToken}
            canWrite={rolesForProduct(
              context.principal,
              search.filters.productId,
            ).some((role) =>
              ["admin", "product_manager_reviewer", "translator"].includes(
                role,
              ),
            )}
            canReview={rolesForProduct(
              context.principal,
              search.filters.productId,
            ).some((role) =>
              ["admin", "product_manager_reviewer"].includes(role),
            )}
            selection={authoringSelection}
            onClearSelection={() => setAuthoringSelection(null)}
            onNew={(open) =>
              runWorkspaceAction(() => {
                resetEditor();
                open();
              }, resultHeading.current)
            }
          />
        )}
        {search.filters.productId && (
          <Glossary
            key={`glossary:${search.filters.productId}`}
            accessToken={context.accessToken}
            productId={search.filters.productId}
            languages={options.languages}
            canManage={rolesForProduct(
              context.principal,
              search.filters.productId,
            ).some((role) =>
              ["admin", "product_manager_reviewer"].includes(role),
            )}
          />
        )}
      </div>
      <TranslationFilters
        filters={search.filters}
        options={options}
        visibleLanguages={search.visibleLanguages}
        availableLanguages={search.availableLanguages.map(
          (language) => language.code,
        )}
        baseLanguage={
          new Set(search.items.map((item) => item.base_language)).size === 1
            ? search.items[0]?.base_language
            : null
        }
        defaultSelectionCapped={search.defaultSelectionCapped}
        availableLanguagesTruncated={search.availableLanguagesTruncated}
        hideProduct={Boolean(lockedProduct)}
        disabled={search.isInitialLoading}
        onChange={changeFilters}
        onClear={clearAll}
        searchControl={
          <div className="flex min-w-0 grow basis-64 items-center gap-1">
            <Label className="sr-only" htmlFor="translation-query">
              Search keys and translations
            </Label>
            <Input
              id="translation-query"
              className="min-h-[44px]"
              placeholder="Enter a key or text"
              title="Search original keys, source text, and translated text"
              value={search.query}
              onChange={(event) => {
                const value = event.target.value;
                runWorkspaceAction(() => {
                  resetEditor();
                  explicitAction.current = true;
                  if (value === "") search.clearQuery();
                  else search.setQuery(value);
                }, event.currentTarget);
              }}
              onKeyDown={(event) => {
                if (event.key === "Enter") {
                  event.preventDefault();
                  explicitAction.current = true;
                  search.submitQuery();
                }
              }}
            />
            <Button
              type="button"
              variant="outline"
              className="min-h-[44px]"
              onClick={() => {
                runWorkspaceAction(
                  () => {
                    resetEditor();
                    explicitAction.current = true;
                    search.clearQuery();
                  },
                  document.activeElement instanceof HTMLElement
                    ? document.activeElement
                    : null,
                );
              }}
            >
              Clear search
            </Button>
          </div>
        }
      />
      <section
        ref={resultRegion}
        className="min-w-0 space-y-(--space-md)"
        aria-labelledby="translation-results-heading"
      >
        <h2
          ref={resultHeading}
          id="translation-results-heading"
          tabIndex={-1}
          className="sr-only"
        >
          Translation results
        </h2>
        {queueMessage && <p role="status">{queueMessage}</p>}
        {context.activeDraft && editorLoad?.status === "error" && (
          <Alert role="alert">
            <AlertTitle>The translation editor could not be loaded</AlertTitle>
            <AlertDescription>
              <Button
                variant="outline"
                onClick={() =>
                  openEditor(editorLoad.groupId, resultHeading.current!)
                }
              >
                Retry editor
              </Button>
            </AlertDescription>
          </Alert>
        )}
        {search.isInitialLoading && visibleItems.length === 0 ? (
          <LoadingResults />
        ) : search.initialError && !context.activeDraft ? (
          <SearchError
            alertRef={alertRef}
            onRetry={() => {
              explicitAction.current = true;
              void search.retryInitial();
            }}
          />
        ) : presentedItems.length === 0 ? (
          <div role="status" className="space-y-(--space-sm)">
            <h3 className="text-heading font-semibold">
              {filtered
                ? "No translations match these filters"
                : "No translations available"}
            </h3>
            <p>
              {filtered
                ? "Change your search or clear the filters to see more translations."
                : "Complete an import for an active product, or choose another authorized product."}
            </p>
            {filtered && (
              <p className="wrap-anywhere">Active criteria: {criteria}</p>
            )}
          </div>
        ) : (
          <div className="min-w-0">
            <TranslationResultList
              items={presentedItems}
              showProductIdentity={!lockedProduct}
              onOpenContext={openContext}
              viewMode={search.filters.viewMode}
              focusLanguage={search.filters.language}
              onRefresh={search.refresh}
              nextCursor={search.nextCursor}
              requestIdentity={search.requestIdentity}
              loadingMore={search.loadingMore}
              loadMoreError={search.loadMoreError}
              onLoadMore={search.loadMore}
              onRetryLoadMore={search.retryLoadMore}
              initialOffset={search.restoredNavigation?.scrollAnchor}
              initialMeasurements={
                search.restoredNavigation &&
                !seed.snapshot?.invalidated &&
                seed.snapshot?.viewportWidth === window.innerWidth
                  ? seed.snapshot.measurements
                  : undefined
              }
              onOpenDetails={(id, measurements) =>
                setSnapshot({
                  ...search.createSnapshot(window.scrollY, id),
                  measurements,
                  viewportWidth: window.innerWidth,
                })
              }
              detailsBasePath={context.detailsBasePath}
              canEditProduct={(productId) =>
                rolesForProduct(context.principal, productId).some((role) =>
                  ["admin", "product_manager_reviewer", "translator"].includes(
                    role,
                  ),
                )
              }
              canEdit={context.principal.roles.some(
                (role) =>
                  role === "admin" ||
                  role === "product_manager_reviewer" ||
                  role === "translator",
              )}
              onEditTranslation={openEditor}
              onAddTranslation={(item, language, trigger) =>
                runWorkspaceAction(() => {
                  resetEditor();
                  setAuthoringSelection({ item, language });
                }, trigger)
              }
              activeEditorGroupId={
                context.activeDraft?.translationGroupId ?? editorLoad?.groupId
              }
              editor={
                context.activeDraft ? (
                  <TranslationEditor
                    key={`${context.accessToken}:${context.activeDraft.translationGroupId}`}
                    accessToken={context.accessToken}
                    draft={context.activeDraft}
                    onDraftChange={context.setActiveDraft}
                    compact
                    continuing={editorLoad?.status === "loading"}
                    onConflict={(response, draft) => {
                      if (response.latest) setConflict({ response, draft });
                    }}
                    onStop={() => {
                      resetEditor();
                      queueMicrotask(() =>
                        editorTrigger.current?.focus({ preventScroll: true }),
                      );
                    }}
                    onSaved={(projection) => {
                      snapshotDirty.current = true;
                      setProposalOverrides((current) => {
                        const next = new Map(current);
                        next.set(projection.translation_group_id, projection);
                        return next;
                      });
                      const draft = context.activeDraft!;
                      const freshDetail = {
                        ...draft.detail,
                        review_eligible: false,
                        pending_change: {
                          version: projection.version,
                          state: projection.state,
                          target_branch: projection.target_branch,
                          target_integrated: projection.target_integrated,
                          reconciliation_required:
                            projection.reconciliation_required,
                          updated_at: projection.updated_at,
                          updated_by: projection.updated_by,
                          values: projection.pending,
                        },
                      };
                      // Context may advance while the editor keeps its captured mutation basis.
                      // Retire reads started before this save, even at the same proposal version.
                      if (
                        selectedContext?.groupId === draft.translationGroupId
                      ) {
                        contextController.current?.abort();
                        contextGeneration.current += 1;
                        setContextLoad({
                          selection: selectedContext,
                          detail: {
                            ...(contextLoad?.detail ?? freshDetail),
                            review_eligible: false,
                            pending_change: freshDetail.pending_change,
                          },
                        });
                      }
                      // Finish editing only after the server confirms the complete proposal.
                      savedEditorFocus.current = draft.translationGroupId;
                      context.setActiveDraft(null);
                      setRetainedItem(
                        presentedItems.find((item) =>
                          item.slots.some(
                            (slot) =>
                              slot.group_id === draft.translationGroupId,
                          ),
                        ) ?? null,
                      );
                      setQueueMessage("Translation saved as Draft.");
                      // Every save changes cursor authority, even in the unfiltered queue.
                      search.refresh();
                      editorController.current?.abort();
                      const controller = new AbortController();
                      editorController.current = controller;
                      const generation = ++editorGeneration.current;
                      const savedContextGeneration = contextGeneration.current;
                      void getTranslationGroup({
                        auth: context.accessToken,
                        path: {
                          translation_group_id: draft.translationGroupId,
                        },
                        signal: controller.signal,
                      })
                        .then((result) => {
                          if (
                            controller.signal.aborted ||
                            generation !== editorGeneration.current ||
                            !result.data ||
                            !completeTranslationDetail(
                              result.data,
                              draft.translationGroupId,
                            ) ||
                            result.data.product_id !== draft.productId ||
                            result.data.language !== draft.language ||
                            (result.data.pending_change?.version ?? 0) <
                              projection.version
                          )
                            return;
                          const detail = result.data;
                          if (
                            savedContextGeneration === contextGeneration.current
                          ) {
                            setContextLoad((loaded) =>
                              loaded?.selection.groupId ===
                              draft.translationGroupId
                                ? { selection: loaded.selection, detail }
                                : loaded,
                            );
                          }
                        })
                        .catch(() => {
                          /* The saved draft stays; context offers an authoritative retry. */
                        });
                      if (context.snapshot)
                        setSnapshot({
                          ...context.snapshot,
                          invalidated: true,
                        });
                    }}
                    returnFocusTo={editorReturnFocusTo}
                  />
                ) : editorLoad?.status === "loading" ? (
                  <p role="status">Loading translation editor</p>
                ) : editorLoad?.status === "error" ? (
                  <Alert role="alert">
                    <AlertTitle>
                      Translation editor could not be loaded
                    </AlertTitle>
                    <AlertDescription>
                      <Button
                        type="button"
                        variant="outline"
                        onClick={() =>
                          editorTrigger.current &&
                          openEditor(editorLoad.groupId, editorTrigger.current)
                        }
                      >
                        Reload editor
                      </Button>
                    </AlertDescription>
                  </Alert>
                ) : null
              }
            />
          </div>
        )}
      </section>
      <AlertDialog
        open={pendingReplacement !== null}
        onOpenChange={(open) => {
          if (!open) {
            replacementFocus.current = pendingReplacement?.trigger ?? null;
            setPendingReplacement(null);
          }
        }}
      >
        <AlertDialogContent
          onCloseAutoFocus={(event) => {
            event.preventDefault();
            queueMicrotask(() =>
              replacementFocus.current?.focus({ preventScroll: true }),
            );
          }}
        >
          <AlertDialogHeader>
            <AlertDialogTitle>Leave without saving?</AlertDialogTitle>
            <AlertDialogDescription>
              Your unsent comment and any unsaved translation changes will be
              lost.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Keep editing</AlertDialogCancel>
            <AlertDialogAction
              variant="destructive"
              disabled={discussionState.submitting}
              onClick={() => {
                const pending = pendingReplacement;
                if (!pending || discussionState.submitting) return;
                replacementFocus.current = null;
                setPendingReplacement(null);
                if (context.activeDraft?.dirty) context.setActiveDraft(null);
                pending.action();
              }}
            >
              Discard changes
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
      {selectedContext && (
        <Sheet
          open={contextOpen}
          onOpenChange={(open) => {
            if (!open) closeContext();
          }}
          modal={false}
        >
          <SheetPrimitive.Portal forceMount>
            <SheetPrimitive.Content
              forceMount
              ref={contextContent}
              tabIndex={-1}
              hidden={!contextOpen}
              inert={!contextOpen}
              className="fixed inset-y-0 right-0 z-40 w-full max-w-xl overflow-y-auto border-l bg-background shadow-xl data-[state=closed]:hidden"
              onOpenAutoFocus={(event) => event.preventDefault()}
              onCloseAutoFocus={(event) => event.preventDefault()}
              onInteractOutside={(event) => event.preventDefault()}
            >
              <div className="flex items-start justify-between gap-3 border-b p-4">
                <div className="min-w-0">
                  <SheetTitle>
                    Translation context · {selectedContext.language}
                  </SheetTitle>
                  <SheetDescription className="wrap-anywhere">
                    {selectedContext.item.raw_key}
                  </SheetDescription>
                </div>
                <SheetClose asChild>
                  <Button
                    variant="outline"
                    className="min-h-[44px]"
                    aria-label="Close translation context"
                  >
                    Close
                  </Button>
                </SheetClose>
              </div>
              {selectedContext.groupId === null ? (
                <section className="space-y-3 p-4" aria-label="Source context">
                  <p
                    lang={selectedContext.language}
                    dir="auto"
                    className="whitespace-pre-wrap wrap-anywhere"
                  >
                    {selectedContext.slot.effective_text ??
                      selectedContext.item.source_text ??
                      "No source text available"}
                  </p>
                  <p>
                    Embedded source text is read-only; edit it in the
                    repository.
                  </p>
                  {selectedContext.slot.provenance && (
                    <p className="wrap-anywhere">
                      {selectedContext.slot.provenance.repository_name} ·{" "}
                      {selectedContext.slot.provenance.path}
                    </p>
                  )}
                </section>
              ) : contextLoad?.detail ? (
                <TranslationContextPanel
                  detail={contextLoad.detail}
                  accessToken={context.accessToken}
                  principal={context.principal}
                  embedded
                  section={selectedContext.section}
                  onSectionChange={(section) =>
                    setSelectedContext({ ...selectedContext, section })
                  }
                  onDraftStateChange={trackDiscussion}
                  dirty={
                    Boolean(contextLoad.failed) ||
                    (context.activeDraft?.translationGroupId ===
                      selectedContext.groupId &&
                      context.activeDraft.dirty)
                  }
                  proposal={proposalOverrides.get(selectedContext.groupId)}
                  onReviewed={(projection) => {
                    if (
                      projection.translation_group_id !==
                        selectedContext.groupId ||
                      projection.language !== selectedContext.language
                    )
                      return;
                    const draft = context.activeDraft;
                    if (
                      draft?.translationGroupId ===
                        projection.translation_group_id &&
                      draft.dirty
                    )
                      return;
                    snapshotDirty.current = true;
                    contextController.current?.abort();
                    contextGeneration.current += 1;
                    setProposalOverrides((current) =>
                      new Map(current).set(
                        projection.translation_group_id,
                        projection,
                      ),
                    );
                    if (
                      draft?.translationGroupId ===
                      projection.translation_group_id
                    )
                      context.setActiveDraft(
                        createActiveTranslationDraft(
                          {
                            ...draft.detail,
                            pending_change: {
                              version: projection.version,
                              state: projection.state,
                              target_branch: projection.target_branch,
                              target_integrated: projection.target_integrated,
                              reconciliation_required:
                                projection.reconciliation_required,
                              updated_at: projection.updated_at,
                              updated_by: projection.updated_by,
                              values: projection.pending,
                            },
                          },
                          context.principal.id,
                        ),
                      );
                    setQueueMessage(
                      `Proposal ${projection.state}. Repository text is unchanged.`,
                    );
                    search.refresh();
                  }}
                />
              ) : contextLoad?.failed ? (
                <Alert role="alert">
                  <AlertTitle>
                    Translation context could not be loaded
                  </AlertTitle>
                  <AlertDescription>
                    <Button
                      variant="outline"
                      onClick={() => fetchContext(selectedContext)}
                    >
                      Retry context
                    </Button>
                  </AlertDescription>
                </Alert>
              ) : (
                <p role="status" className="p-4">
                  Loading translation context
                </p>
              )}
            </SheetPrimitive.Content>
          </SheetPrimitive.Portal>
        </Sheet>
      )}
    </>
  );
}

function SearchOptions({
  context,
  requestedProductId,
  requestedLanguage,
}: {
  context: TranslationsWorkspaceContext;
  requestedProductId: string | null;
  requestedLanguage: string | null;
}) {
  const locationKey = useLocation().key;
  const snapshotMatches =
    context.snapshot &&
    (requestedProductId === null ||
      context.snapshot.filters.productId === requestedProductId) &&
    ((context.snapshot as LocatedSnapshot).searchLocationKey === locationKey ||
      requestedLanguage === null);
  const [pendingQuery, setPendingQuery] = useState(
    snapshotMatches ? context.snapshot!.query : "",
  );
  const queryRef = useRef(pendingQuery);
  const retryAction = useRef(false);
  const optionsAlert = useRef<HTMLDivElement>(null);
  const [seed, setSeed] = useState<Seed | null>(() => {
    if (context.snapshot && snapshotMatches) {
      return {
        query: context.snapshot.query,
        filters: context.snapshot.filters,
        snapshot: context.snapshot,
      };
    }
    if (requestedProductId !== null || requestedLanguage !== null) {
      return {
        query: "",
        filters: {
          ...DEFAULT_FILTERS,
          productId: requestedProductId,
          language: requestedLanguage,
          ...(requestedLanguage
            ? { viewMode: "bilingual" as const, visibleLanguages: null }
            : {}),
        },
        snapshot: null,
        focusLanguage: requestedLanguage,
      };
    }
    return null;
  });
  const [request, setRequest] = useState(0);
  const [load, setLoad] = useState<{
    request: number;
    ready?: ReadyOptions;
    failed?: boolean;
  }>({ request: 0 });
  const ready = load.request === request ? load.ready : undefined;
  const failed = load.request === request && load.failed;
  useEffect(() => {
    if (!failed || !retryAction.current) return;
    let active = true;
    queueMicrotask(() => {
      if (active) optionsAlert.current?.focus();
    });
    return () => {
      active = false;
    };
  }, [failed]);
  const principalId = context.principal.id;
  const accessToken = context.accessToken;
  const lockedProduct = context.lockedProduct;
  useEffect(() => {
    const controller = new AbortController();
    void (async () => {
      try {
        const initialProduct = lockedProduct?.id ?? null;
        const global = await listTranslationOptions({
          auth: accessToken,
          ...(initialProduct ? { query: { product_id: initialProduct } } : {}),
          signal: controller.signal,
        });
        if (controller.signal.aborted) return;
        if (!global.data) throw new Error("Options unavailable");
        let choices = global.data;
        let preferences;
        if (seed && (seed.snapshot || seed.filters.viewMode))
          preferences = sanitizeTranslationPreferences(seed.filters, choices);
        else {
          try {
            preferences = loadTranslationPreferences(
              localStorage,
              principalId,
              choices,
              lockedProduct?.id,
            );
          } catch {
            preferences = { productId: null, language: null };
          }
          if (seed)
            preferences = { ...preferences, productId: seed.filters.productId };
        }
        if (lockedProduct) {
          const authorized = choices.products.some(
            (product) => product.id === lockedProduct.id,
          );
          if (!authorized) throw new Error("Product unavailable");
          preferences = { ...preferences, productId: lockedProduct.id };
        }
        if (
          preferences.productId !== null &&
          preferences.productId !== initialProduct
        ) {
          const scoped = await listTranslationOptions({
            auth: accessToken,
            query: { product_id: preferences.productId },
            signal: controller.signal,
          });
          if (controller.signal.aborted) return;
          if (!scoped.data) throw new Error("Options unavailable");
          choices = scoped.data;
          preferences = sanitizeTranslationPreferences(
            {
              ...preferences,
              language:
                seed && (seed.snapshot || seed.filters.viewMode)
                  ? seed.filters.language
                  : preferences.language,
            },
            choices,
          );
        }
        const filters = {
          ...DEFAULT_FILTERS,
          ...seed?.filters,
          ...preferences,
        };
        const snapshot = seed?.snapshot;
        const validSnapshot =
          snapshot &&
          snapshot.query === queryRef.current &&
          translationSearchIdentity(snapshot.query, snapshot.filters) ===
            translationSearchIdentity(queryRef.current, filters);
        setLoad({
          request,
          ready: {
            options: choices,
            seed: {
              query: queryRef.current,
              filters,
              snapshot: validSnapshot ? snapshot : null,
              focusControl: retryAction.current ? "query" : seed?.focusControl,
              focusLanguage: seed?.focusLanguage ? filters.language : null,
            },
          },
        });
      } catch {
        if (!controller.signal.aborted) setLoad({ request, failed: true });
      }
    })();
    return () => controller.abort();
  }, [accessToken, lockedProduct, principalId, request, seed]);
  const restart = useCallback((next: Seed) => {
    retryAction.current = false;
    queryRef.current = next.query;
    setPendingQuery(next.query);
    setSeed(next);
    setRequest((value) => value + 1);
  }, []);
  return (
    <div className="grid min-w-0 gap-(--space-xl)">
      <header className="space-y-(--space-sm)">
        {lockedProduct ? (
          <h2 className="text-display font-semibold">Strings</h2>
        ) : (
          <h1 className="text-display font-semibold">Translations</h1>
        )}
      </header>
      {ready ? (
        <ResolvedSearch
          key={request}
          ready={ready}
          context={context}
          onRestart={restart}
        />
      ) : (
        <>
          <div
            className="space-y-(--space-sm) rounded-lg bg-secondary p-(--space-md)"
            aria-busy={!failed}
          >
            <Label htmlFor="translation-query">
              Search keys and translations
            </Label>
            <Input
              id="translation-query"
              className="min-h-[44px]"
              placeholder="Enter a key or text"
              aria-describedby="translation-query-help"
              value={pendingQuery}
              onChange={(event) => {
                queryRef.current = event.target.value;
                setPendingQuery(event.target.value);
              }}
            />
            <p
              id="translation-query-help"
              className="text-body text-muted-foreground"
            >
              Searches original keys, source text, and translated text.
            </p>
          </div>
          <TranslationFilters
            filters={
              seed?.filters ?? {
                ...DEFAULT_FILTERS,
                productId: lockedProduct?.id ?? null,
              }
            }
            options={load.ready?.options ?? EMPTY_OPTIONS}
            disabled
            hideProduct={Boolean(lockedProduct)}
            onChange={() => {}}
            onClear={() =>
              restart({
                query: "",
                filters: {
                  ...DEFAULT_FILTERS,
                  productId: lockedProduct?.id ?? null,
                },
              })
            }
          />
          {failed ? (
            <SearchError
              alertRef={optionsAlert}
              onRetry={() => {
                retryAction.current = true;
                setRequest((value) => value + 1);
              }}
            />
          ) : (
            <LoadingResults />
          )}
        </>
      )}
    </div>
  );
}

export function TranslationSearchPage() {
  const context = useOutletContext<TranslationsWorkspaceContext>();
  const locationKey = useLocation().key;
  const [searchParams] = useSearchParams();
  const requestedProductId =
    context.lockedProduct?.id ??
    (searchParams.get("product_id")?.trim() || null) ??
    null;
  const requestedLanguage = searchParams.get("language")?.trim() || null;
  return (
    <SearchOptions
      key={JSON.stringify([
        context.accessToken,
        context.principal.roles,
        requestedProductId,
        requestedLanguage,
        locationKey,
      ])}
      context={context}
      requestedProductId={requestedProductId}
      requestedLanguage={requestedLanguage}
    />
  );
}
