import {
  useCallback,
  createContext,
  useContext,
  useMemo,
  useState,
  type PropsWithChildren,
} from "react";

import {
  issueToken,
  readCurrentUser,
  type CurrentUserResponse,
} from "../../api/client";

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
  const [state, setState] = useState<SessionState>({ status: "signed_out" });

  const login = useCallback(async (credentials: LoginCredentials) => {
    const tokenResult = await issueToken({
      body: {
        username: credentials.email,
        password: credentials.password,
      },
    });
    const authority = tokenResult.data;
    if (authority === undefined || authority.must_change_password) {
      setState({ status: "signed_out" });
      return;
    }

    const identityResult = await readCurrentUser({
      auth: authority.access_token,
    });
    if (identityResult.data === undefined) {
      setState({ status: "signed_out" });
      return;
    }
    setState({
      status: "authenticated",
      accessToken: authority.access_token,
      principal: identityResult.data,
    });
  }, []);

  const value = useMemo<SessionValue>(
    () => ({
      state,
      login,
      changePassword: notImplemented,
      restoreSession: notImplemented,
      logout: notImplemented,
    }),
    [login, state],
  );

  return (
    <SessionContext.Provider value={value}>{children}</SessionContext.Provider>
  );
}

export function useSession(): SessionValue {
  const session = useContext(SessionContext);
  if (session === null) {
    throw new Error("useSession must be used within SessionProvider");
  }
  return session;
}
