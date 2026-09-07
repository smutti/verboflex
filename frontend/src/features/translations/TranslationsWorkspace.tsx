import { useCallback, useState } from "react";
import { Outlet } from "react-router-dom";
import type { CurrentUserResponse } from "../../api/client";
import type { TranslationProductOptionResponse } from "../../api/client";
import type { TranslationSearchSnapshot } from "./useTranslationSearch";

export interface TranslationsWorkspaceContext {
  accessToken: string;
  principal: CurrentUserResponse;
  snapshot: TranslationSearchSnapshot | null;
  setSnapshot: (snapshot: TranslationSearchSnapshot | null) => void;
  lockedProduct?: TranslationProductOptionResponse;
  detailsBasePath: string;
  searchPath: string;
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
  return (
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
        } satisfies TranslationsWorkspaceContext
      }
    />
  );
}

export function TranslationsWorkspace(props: TranslationsWorkspaceProps) {
  return (
    <PrincipalWorkspace
      key={`${props.principal.id}:${props.lockedProduct?.id ?? "all"}`}
      {...props}
    />
  );
}
