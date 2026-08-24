import {
  useCallback,
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  type PropsWithChildren,
} from "react";

import {
  changePassword as generatedChangePassword,
  logout as generatedLogout,
  issueToken,
  readCurrentUser,
  refreshAccessToken,
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

const SessionContext = createContext<SessionValue | null>(null);

export interface SessionProviderProps extends PropsWithChildren {
  restoreOnMount?: boolean;
}

export function SessionProvider({
  children,
  restoreOnMount = true,
}: SessionProviderProps) {
  const [state, setState] = useState<SessionState>(
    restoreOnMount ? { status: "checking_session" } : { status: "signed_out" },
  );

  const login = useCallback(async (credentials: LoginCredentials) => {
    const tokenResult = await issueToken({
      body: {
        username: credentials.email,
        password: credentials.password,
      },
    });
    const authority = tokenResult.data;
    if (authority === undefined) {
      setState({ status: "signed_out" });
      return;
    }
    if (authority.must_change_password) {
      setState({
        status: "password_change_required",
        accessToken: authority.access_token,
      });
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

  const changePassword = useCallback(
    async (passwords: PasswordChange) => {
      if (state.status !== "password_change_required") {
        return;
      }
      const result = await generatedChangePassword({
        auth: state.accessToken,
        body: {
          current_password: passwords.currentPassword,
          new_password: passwords.newPassword,
        },
      });
      if (result.error === undefined) {
        setState({ status: "signed_out" });
      }
    },
    [state],
  );

  const restoreSession = useCallback(async () => {
    setState({ status: "checking_session" });
    let refreshResult: Awaited<ReturnType<typeof refreshAccessToken>>;
    try {
      refreshResult = await refreshAccessToken();
    } catch {
      setState({ status: "signed_out" });
      return;
    }
    const authority = refreshResult.data;
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

  useEffect(() => {
    if (restoreOnMount) {
      void restoreSession();
    }
  }, [restoreOnMount, restoreSession]);

  const logout = useCallback(async () => {
    try {
      await generatedLogout();
    } finally {
      setState({ status: "signed_out" });
    }
  }, []);

  const value = useMemo<SessionValue>(
    () => ({
      state,
      login,
      changePassword,
      restoreSession,
      logout,
    }),
    [changePassword, login, logout, restoreSession, state],
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
