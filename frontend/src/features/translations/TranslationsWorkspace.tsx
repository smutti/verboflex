import { t, useUiLanguage } from "@/i18n";
import { useCallback, useRef, useState } from "react";
import { Outlet } from "react-router-dom";
import type { CurrentUserResponse } from "../../api/client";
import type { TranslationProductOptionResponse } from "../../api/client";
import type { TranslationSearchSnapshot } from "./useTranslationSearch";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "../../components/ui/alert-dialog";
import { useOptionalDirtyFormNavigationGuard } from "../../components/navigation/DirtyFormNavigationGuard";
import type { ActiveTranslationDraft } from "./TranslationEditor";

export interface TranslationsWorkspaceContext {
  accessToken: string;
  principal: CurrentUserResponse;
  snapshot: TranslationSearchSnapshot | null;
  setSnapshot: (snapshot: TranslationSearchSnapshot | null) => void;
  lockedProduct?: TranslationProductOptionResponse;
  detailsBasePath: string;
  searchPath: string;
  activeDraft: ActiveTranslationDraft | null;
  setActiveDraft: (draft: ActiveTranslationDraft | null) => void;
  runDraftGuardedAction: (
    action: () => void,
    trigger?: HTMLElement | null,
  ) => void;
}

interface TranslationsWorkspaceProps {
  accessToken: string;
  principal: CurrentUserResponse;
  lockedProduct?: TranslationProductOptionResponse;
  detailsBasePath?: string;
  searchPath?: string;
}

function PrincipalWorkspace({
  accessToken,
  principal,
  lockedProduct,
  detailsBasePath = "/translations",
  searchPath = "/translations",
}: TranslationsWorkspaceProps) {
  useUiLanguage();
  const [memory, setMemory] = useState<{
    token: string;
    snapshot: TranslationSearchSnapshot | null;
  }>({ token: accessToken, snapshot: null });
  const setSnapshot = useCallback(
    (snapshot: TranslationSearchSnapshot | null) =>
      setMemory({ token: accessToken, snapshot }),
    [accessToken],
  );
  const snapshot =
    memory.token === accessToken || !memory.snapshot
      ? memory.snapshot
      : { ...memory.snapshot, pages: [] };
  const draftAuthority = JSON.stringify([accessToken, principal.roles]);
  const [draftMemory, setDraftMemory] = useState<{
    authority: string;
    draft: ActiveTranslationDraft | null;
  }>({ authority: draftAuthority, draft: null });
  const activeDraft =
    draftMemory.authority === draftAuthority ? draftMemory.draft : null;
  const setActiveDraft = useCallback(
    (draft: ActiveTranslationDraft | null) =>
      setDraftMemory({ authority: draftAuthority, draft }),
    [draftAuthority],
  );
  const [pendingMemory, setPendingAction] = useState<{
    authority: string;
    action: () => void;
    trigger: HTMLElement | null;
  } | null>(null);
  const pendingAction =
    pendingMemory?.authority === draftAuthority ? pendingMemory : null;
  const restoreFocus = useRef<HTMLElement | null>(null);
  useOptionalDirtyFormNavigationGuard(
    `translation-editor:${principal.id}:${lockedProduct?.id ?? "all"}`,
    activeDraft?.dirty ?? false,
  );
  const runDraftGuardedAction = useCallback(
    (action: () => void, trigger: HTMLElement | null = null) => {
      if (!activeDraft?.dirty) {
        action();
        return;
      }
      setPendingAction({ action, trigger, authority: draftAuthority });
    },
    [activeDraft?.dirty, draftAuthority],
  );
  return (
    <>
      <Outlet
        context={
          {
            accessToken,
            principal,
            snapshot,
            setSnapshot,
            lockedProduct,
            detailsBasePath,
            searchPath,
            activeDraft,
            setActiveDraft,
            runDraftGuardedAction,
          } satisfies TranslationsWorkspaceContext
        }
      />
      <AlertDialog
        open={pendingAction !== null}
        onOpenChange={(open) => {
          if (!open) {
            restoreFocus.current = pendingAction?.trigger ?? null;
            setPendingAction(null);
          }
        }}
      >
        <AlertDialogContent
          onCloseAutoFocus={(event) => {
            event.preventDefault();
            const target = restoreFocus.current;
            restoreFocus.current = null;
            queueMicrotask(() => target?.focus({ preventScroll: true }));
          }}
        >
          <AlertDialogHeader>
            <AlertDialogTitle>{t("Leave without saving?")}</AlertDialogTitle>
            <AlertDialogDescription>
              {t("Your unsaved translation changes will be lost.")}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{t("Keep editing")}</AlertDialogCancel>
            <AlertDialogAction
              variant="destructive"
              onClick={() => {
                const pending = pendingAction;
                if (!pending) return;
                setPendingAction(null);
                setActiveDraft(null);
                pending.action();
              }}
            >
              {t("Discard changes")}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}

export function TranslationsWorkspace(props: TranslationsWorkspaceProps) {
  useUiLanguage();
  return (
    <PrincipalWorkspace
      key={`${props.principal.id}:${props.lockedProduct?.id ?? "all"}`}
      {...props}
    />
  );
}
