import type { ReactNode } from "react";
import { Navigate, Route, Routes } from "react-router-dom";

import { App } from "./App";
import { AppShell } from "./components/layout/AppShell";
import { Alert, AlertDescription, AlertTitle } from "./components/ui/alert";
import { Button } from "./components/ui/button";
import { Skeleton } from "./components/ui/skeleton";
import { AdminAccessDenied } from "./features/admin/AdminAccessDenied";
import { ChangePasswordPage } from "./features/auth/ChangePasswordPage";
import { LoginPage } from "./features/auth/LoginPage";
import { useSession, type SessionState } from "./features/auth/session";

export type AdminRouteState =
  | { status: "ready" }
  | { status: "loading" }
  | { status: "error"; onRetry: () => void };

export interface SessionRoutesProps {
  state: SessionState;
  loginElement: ReactNode;
  changePasswordElement: ReactNode;
  ordinaryElement: ReactNode;
  adminElement?: ReactNode;
  adminRouteState?: AdminRouteState;
  accessDeniedElement?: ReactNode;
}

function AdminRouteContent({
  children,
  state,
}: {
  children: ReactNode;
  state: AdminRouteState;
}) {
  if (state.status === "loading") {
    return (
      <section
        className="grid max-w-3xl gap-4"
        role="status"
        aria-live="polite"
      >
        <Skeleton className="h-8 w-52 max-w-full" />
        <Skeleton className="h-24 w-full" />
        <span>Loading administration page</span>
      </section>
    );
  }

  if (state.status === "error") {
    return (
      <Alert variant="destructive" className="max-w-3xl">
        <AlertTitle>Administration page unavailable</AlertTitle>
        <AlertDescription>
          <p>
            We could not load this page. Retry without leaving the
            administration area.
          </p>
          <Button type="button" variant="outline" onClick={state.onRetry}>
            Retry loading page
          </Button>
        </AlertDescription>
      </Alert>
    );
  }

  return children;
}

export function SessionRoutes({
  state,
  loginElement,
  changePasswordElement,
  ordinaryElement,
  adminElement,
  adminRouteState = { status: "ready" },
  accessDeniedElement,
}: SessionRoutesProps) {
  if (state.status === "checking_session") {
    return (
      <main className="flex min-h-screen items-center justify-center px-6">
        <div
          className="grid w-full max-w-sm gap-4 text-center"
          role="status"
          aria-live="polite"
        >
          <Skeleton className="mx-auto h-5 w-48" />
          <Skeleton className="mx-auto h-4 w-64" />
          <span>Checking session</span>
        </div>
      </main>
    );
  }

  if (state.status === "signed_out") {
    return (
      <Routes>
        <Route path="/login" element={loginElement} />
        <Route path="*" element={<Navigate replace to="/login" />} />
      </Routes>
    );
  }

  if (state.status === "password_change_required") {
    return (
      <Routes>
        <Route path="/change-password" element={changePasswordElement} />
        <Route path="*" element={<Navigate replace to="/change-password" />} />
      </Routes>
    );
  }

  const isAdmin = state.principal.roles.includes("admin");
  const deniedElement = accessDeniedElement ?? <AdminAccessDenied />;
  const guardedAdminElement = isAdmin ? (
    <AdminRouteContent state={adminRouteState}>
      {adminElement ?? ordinaryElement}
    </AdminRouteContent>
  ) : (
    deniedElement
  );

  return (
    <Routes>
      <Route path="/" element={ordinaryElement} />
      <Route path="/admin/users" element={guardedAdminElement} />
      <Route
        path="/admin/*"
        element={
          isAdmin ? <Navigate replace to="/admin/users" /> : deniedElement
        }
      />
      <Route path="*" element={<Navigate replace to="/" />} />
    </Routes>
  );
}

export function AppRouter() {
  const { logout, state } = useSession();
  const authenticatedShellProps =
    state.status === "authenticated"
      ? {
          accessToken: state.accessToken,
          onLogout: logout,
          principal: state.principal,
        }
      : null;

  return (
    <SessionRoutes
      state={state}
      loginElement={<LoginPage />}
      changePasswordElement={<ChangePasswordPage />}
      ordinaryElement={<App />}
      adminElement={
        authenticatedShellProps === null ? null : (
          <AppShell {...authenticatedShellProps}>
            <section className="grid gap-2" aria-labelledby="admin-users-title">
              <h1 id="admin-users-title" className="text-display font-semibold">
                Users
              </h1>
              <p className="text-muted-foreground">
                Manage internal users, roles, and account access.
              </p>
            </section>
          </AppShell>
        )
      }
      accessDeniedElement={
        authenticatedShellProps === null ? null : (
          <AppShell {...authenticatedShellProps}>
            <AdminAccessDenied />
          </AppShell>
        )
      }
    />
  );
}
