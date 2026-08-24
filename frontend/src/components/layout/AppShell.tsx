import type { CurrentUserResponse } from "../../api/client";

export interface AppShellProps {
  accessToken: string;
  onLogout: () => Promise<void>;
  principal: CurrentUserResponse;
}

export function AppShell(_props: AppShellProps) {
  return <p>Dashboard shell not implemented</p>;
}
