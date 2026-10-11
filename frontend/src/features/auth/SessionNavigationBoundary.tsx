import type { PropsWithChildren } from "react";

import { DirtyFormNavigationProvider } from "../../components/navigation/DirtyFormNavigationGuard";
import { useSession } from "./session";

export function SessionNavigationBoundary({ children }: PropsWithChildren) {
  const { state } = useSession();
  const authority =
    state.status === "authenticated"
      ? `${state.status}:${state.principal.id}`
      : state.status;

  // Discard the old user's navigation blocker and editor state before an
  // authentication redirect. A revoked session cannot keep editing a dirty form.
  return (
    <DirtyFormNavigationProvider key={authority}>
      {children}
    </DirtyFormNavigationProvider>
  );
}
