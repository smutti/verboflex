import { AppShell } from "./components/layout/AppShell";
import { useSession } from "./features/auth/session";
import { WorkspaceOverviewPage } from "./features/workspace/WorkspaceOverviewPage";

export function App() {
  const { logout, state } = useSession();

  if (state.status !== "authenticated") {
    return null;
  }

  return (
    <AppShell
      accessToken={state.accessToken}
      onLogout={logout}
      principal={state.principal}
    >
      <WorkspaceOverviewPage
        accessToken={state.accessToken}
        principal={state.principal}
      />
    </AppShell>
  );
}
