import {
  createContext,
  useContext,
  type PropsWithChildren,
} from "react";

import type { CurrentUserResponse } from "../../api/client";

export type SessionState =
  | { status: "checking_session" }
  | { status: "signed_out" }
  | { status: "password_change_required"; accessToken: string }
  | {
      status: "authenticated";
      accessToken: string;
      principal: CurrentUserResponse;
    };

export interface LoginCredentials {
  email: string;
  password: string;
}

export interface PasswordChange {
  currentPassword: string;
  newPassword: string;
}

export interface SessionValue {
  state: SessionState;
  login: (credentials: LoginCredentials) => Promise<void>;
  changePassword: (passwords: PasswordChange) => Promise<void>;
  restoreSession: () => Promise<void>;
  logout: () => Promise<void>;
}

const notImplemented = async (): Promise<void> => {
  throw new Error("Session transition not implemented");
};

const SessionContext = createContext<SessionValue | null>(null);

export interface SessionProviderProps extends PropsWithChildren {
  restoreOnMount?: boolean;
}

export function SessionProvider({ children }: SessionProviderProps) {
  return (
    <SessionContext.Provider
      value={{
        state: { status: "signed_out" },
        login: notImplemented,
        changePassword: notImplemented,
        restoreSession: notImplemented,
        logout: notImplemented,
      }}
    >
      {children}
    </SessionContext.Provider>
  );
}

export function useSession(): SessionValue {
  const session = useContext(SessionContext);
  if (session === null) {
    throw new Error("useSession must be used within SessionProvider");
  }
  return session;
}
