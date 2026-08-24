import { AppShell } from "./components/layout/AppShell";
import { useSession } from "./features/auth/session";

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
    />
  );
}
