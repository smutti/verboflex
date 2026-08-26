import type { ReactNode } from "react";
import { Navigate, Route, Routes } from "react-router-dom";

import { App } from "./App";
import { Skeleton } from "./components/ui/skeleton";
import { ChangePasswordPage } from "./features/auth/ChangePasswordPage";
import { LoginPage } from "./features/auth/LoginPage";
import { useSession, type SessionState } from "./features/auth/session";

export interface SessionRoutesProps {
  state: SessionState;
  loginElement: ReactNode;
  changePasswordElement: ReactNode;
  ordinaryElement: ReactNode;
}

export function SessionRoutes({
  state,
  loginElement,
  changePasswordElement,
  ordinaryElement,
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

  return (
    <Routes>
      <Route path="/" element={ordinaryElement} />
      <Route path="*" element={<Navigate replace to="/" />} />
    </Routes>
  );
}

export function AppRouter() {
  const { state } = useSession();

  return (
    <SessionRoutes
      state={state}
      loginElement={<LoginPage />}
      changePasswordElement={<ChangePasswordPage />}
      ordinaryElement={<App />}
    />
  );
}
