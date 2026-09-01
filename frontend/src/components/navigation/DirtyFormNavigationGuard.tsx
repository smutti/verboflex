import type { ReactNode } from "react";

export function DirtyFormNavigationProvider({
  children,
}: {
  children: ReactNode;
}) {
  return children;
}

export function useDirtyFormNavigationGuard(_formId: string, _dirty: boolean) {}
