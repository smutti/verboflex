import type { ReactNode } from "react";

import type { SessionState } from "./features/auth/session";

export interface SessionRoutesProps {
  state: SessionState;
  loginElement: ReactNode;
  changePasswordElement: ReactNode;
  ordinaryElement: ReactNode;
}

export function SessionRoutes(_props: SessionRoutesProps) {
  return null;
}
