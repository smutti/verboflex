import { useCallback, useState } from "react";
import { Outlet } from "react-router-dom";
import type { CurrentUserResponse } from "../../api/client";
import type { TranslationSearchSnapshot } from "./useTranslationSearch";

export interface TranslationsWorkspaceContext {
  accessToken: string;
  principal: CurrentUserResponse;
  snapshot: TranslationSearchSnapshot | null;
  setSnapshot: (snapshot: TranslationSearchSnapshot | null) => void;
}

interface TranslationsWorkspaceProps {
  accessToken: string;
  principal: CurrentUserResponse;
}

function PrincipalWorkspace({
  accessToken,
  principal,
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
        } satisfies TranslationsWorkspaceContext
      }
    />
  );
}

export function TranslationsWorkspace(props: TranslationsWorkspaceProps) {
  return <PrincipalWorkspace key={props.principal.id} {...props} />;
}
