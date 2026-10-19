import { t, useUiLanguage } from "@/i18n";
import {
  createContext,
  type ReactNode,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { useBeforeUnload, useBlocker } from "react-router-dom";

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";

type DirtyFormRegistry = {
  setDirty: (formId: string, dirty: boolean) => void;
  unregister: (formId: string) => void;
};

type PendingTransaction = {
  consumed: boolean;
  locationIdentity: string;
  proceed: () => void;
  reset: () => void;
  token: number;
  trigger: HTMLElement | null;
};

const DirtyFormNavigationContext = createContext<DirtyFormRegistry | null>(
  null,
);

function connectedActiveElement() {
  const activeElement = document.activeElement;
  return activeElement instanceof HTMLElement &&
    activeElement !== document.body &&
    activeElement.isConnected
    ? activeElement
    : null;
}

export function DirtyFormNavigationProvider({
  children,
}: {
  children: ReactNode;
}) {
  useUiLanguage();
  const [dirtyForms, setDirtyForms] = useState<ReadonlySet<string>>(
    () => new Set(),
  );
  const [openTransactionToken, setOpenTransactionToken] = useState<
    number | null
  >(null);
  const pendingTransactionRef = useRef<PendingTransaction | null>(null);
  const focusTargetRef = useRef<HTMLElement | null>(null);
  const nextTransactionTokenRef = useRef(0);
  const isDirty = dirtyForms.size > 0;

  const setDirty = useCallback((formId: string, dirty: boolean) => {
    setDirtyForms((current) => {
      const next = new Set(current);
      if (dirty) {
        next.add(formId);
      } else {
        next.delete(formId);
      }
      if (
        next.size === current.size &&
        next.has(formId) === current.has(formId)
      ) {
        return current;
      }
      return next;
    });
  }, []);

  const unregister = useCallback((formId: string) => {
    setDirtyForms((current) => {
      if (!current.has(formId)) {
        return current;
      }
      const next = new Set(current);
      next.delete(formId);
      return next;
    });
  }, []);

  const registry = useMemo(
    () => ({ setDirty, unregister }),
    [setDirty, unregister],
  );
  const blocker = useBlocker(useCallback(() => isDirty, [isDirty]));

  useBeforeUnload(
    useCallback(
      (event) => {
        if (!isDirty) {
          return;
        }
        event.preventDefault();
        event.returnValue = "";
      },
      [isDirty],
    ),
  );

  useEffect(() => {
    if (blocker.state !== "blocked" || pendingTransactionRef.current !== null) {
      return;
    }

    const token = nextTransactionTokenRef.current + 1;
    nextTransactionTokenRef.current = token;
    pendingTransactionRef.current = {
      consumed: false,
      locationIdentity: `${blocker.location.key}:${blocker.location.pathname}${blocker.location.search}${blocker.location.hash}`,
      proceed: blocker.proceed,
      reset: blocker.reset,
      token,
      trigger: connectedActiveElement(),
    };
    setOpenTransactionToken(token);
  }, [blocker]);

  const keepEditing = useCallback(() => {
    const pending = pendingTransactionRef.current;
    if (pending === null || pending.consumed) {
      return;
    }
    pending.consumed = true;
    focusTargetRef.current = pending.trigger;
    pending.reset();
    pendingTransactionRef.current = null;
    setOpenTransactionToken(null);
  }, []);

  const discardChanges = useCallback(() => {
    const pending = pendingTransactionRef.current;
    if (pending === null || pending.consumed) {
      return;
    }
    pending.consumed = true;
    focusTargetRef.current = null;
    pending.proceed();
    pendingTransactionRef.current = null;
    setOpenTransactionToken(null);
  }, []);

  useEffect(() => {
    if (isDirty) {
      return;
    }
    const pending = pendingTransactionRef.current;
    if (pending === null || pending.consumed) {
      return;
    }
    pending.consumed = true;
    pending.reset();
    pendingTransactionRef.current = null;
    setOpenTransactionToken(null);
  }, [isDirty]);

  useEffect(
    () => () => {
      const pending = pendingTransactionRef.current;
      if (pending !== null && !pending.consumed) {
        pending.consumed = true;
        pending.reset();
      }
      pendingTransactionRef.current = null;
      focusTargetRef.current = null;
    },
    [],
  );

  const restoreFocus = useCallback((event: Event) => {
    event.preventDefault();
    const focusTarget = focusTargetRef.current;
    focusTargetRef.current = null;
    queueMicrotask(() => {
      if (focusTarget?.isConnected) {
        focusTarget.focus();
      }
    });
  }, []);

  return (
    <DirtyFormNavigationContext.Provider value={registry}>
      {children}
      <AlertDialog
        open={openTransactionToken !== null}
        onOpenChange={keepEditing}
      >
        <AlertDialogContent onCloseAutoFocus={restoreFocus}>
          <AlertDialogHeader>
            <AlertDialogTitle>{t("Leave without saving?")}</AlertDialogTitle>
            <AlertDialogDescription>
              {t("Your unsaved entries on this page will be lost.")}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel onClick={keepEditing}>
              {t("Keep editing")}
            </AlertDialogCancel>
            <AlertDialogAction variant="destructive" onClick={discardChanges}>
              {t("Discard changes")}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </DirtyFormNavigationContext.Provider>
  );
}

// eslint-disable-next-line react-refresh/only-export-components
export function useDirtyFormNavigationGuard(formId: string, dirty: boolean) {
  const registry = useContext(DirtyFormNavigationContext);
  if (registry === null) {
    throw new Error(
      "useDirtyFormNavigationGuard requires DirtyFormNavigationProvider",
    );
  }

  useEffect(() => {
    registry.setDirty(formId, dirty);
    return () => registry.unregister(formId);
  }, [dirty, formId, registry]);
}

// Feature workspaces are also rendered in isolated component tests and static
// previews where the application-level provider is intentionally absent.
// eslint-disable-next-line react-refresh/only-export-components
export function useOptionalDirtyFormNavigationGuard(
  formId: string,
  dirty: boolean,
) {
  const registry = useContext(DirtyFormNavigationContext);
  useEffect(() => {
    if (registry === null) return;
    registry.setDirty(formId, dirty);
    return () => registry.unregister(formId);
  }, [dirty, formId, registry]);
}
