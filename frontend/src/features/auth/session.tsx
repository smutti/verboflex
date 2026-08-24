import {
  useCallback,
  createContext,
  useContext,
  useEffect,
  useMemo,
  useRef,
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

export type SessionEvent =
  | { type: "check_session" }
  | { type: "sign_out" }
  | { type: "restrict"; accessToken: string }
  | {
      type: "authenticate";
      accessToken: string;
      principal: CurrentUserResponse;
    };

export function transitionSession(
  _state: SessionState,
  event: SessionEvent,
): SessionState {
  switch (event.type) {
    case "check_session":
      return { status: "checking_session" };
    case "sign_out":
      return { status: "signed_out" };
    case "restrict":
      return event.accessToken.length > 0
        ? {
            status: "password_change_required",
            accessToken: event.accessToken,
          }
        : { status: "signed_out" };
    case "authenticate":
      return event.accessToken.length > 0 &&
        !event.principal.must_change_password
        ? {
            status: "authenticated",
            accessToken: event.accessToken,
            principal: event.principal,
          }
        : { status: "signed_out" };
  }
}

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
  const operationVersion = useRef(0);

  const login = useCallback(async (credentials: LoginCredentials) => {
    const version = operationVersion.current + 1;
    operationVersion.current = version;
    const tokenResult = await issueToken({
      body: {
        username: credentials.email,
        password: credentials.password,
      },
    });
    if (operationVersion.current !== version) {
      return;
    }
    const authority = tokenResult.data;
    if (authority === undefined) {
      setState((current) =>
        transitionSession(current, { type: "sign_out" }),
      );
      throw new Error("Session action failed");
    }
    if (authority.must_change_password) {
      setState((current) =>
        transitionSession(current, {
          type: "restrict",
          accessToken: authority.access_token,
        }),
      );
      return;
    }

    const identityResult = await readCurrentUser({
      auth: authority.access_token,
    });
    if (operationVersion.current !== version) {
      return;
    }
    if (identityResult.data === undefined) {
      setState((current) =>
        transitionSession(current, { type: "sign_out" }),
      );
      return;
    }
    setState((current) =>
      transitionSession(current, {
        type: "authenticate",
        accessToken: authority.access_token,
        principal: identityResult.data,
      }),
    );
  }, []);

  const changePassword = useCallback(
    async (passwords: PasswordChange) => {
      if (state.status !== "password_change_required") {
        return;
      }
      const version = operationVersion.current + 1;
      operationVersion.current = version;
      const result = await generatedChangePassword({
        auth: state.accessToken,
        body: {
          current_password: passwords.currentPassword,
          new_password: passwords.newPassword,
        },
      });
      if (operationVersion.current !== version) {
        return;
      }
      if (result.error !== undefined) {
        throw new Error("Session action failed");
      }
      setState((current) =>
        transitionSession(current, { type: "sign_out" }),
      );
    },
    [state],
  );

  const restoreSession = useCallback(async () => {
    const version = operationVersion.current + 1;
    operationVersion.current = version;
    setState((current) =>
      transitionSession(current, { type: "check_session" }),
    );
    let refreshResult: Awaited<ReturnType<typeof refreshAccessToken>>;
    try {
      refreshResult = await refreshAccessToken();
    } catch {
      if (operationVersion.current === version) {
        setState((current) =>
          transitionSession(current, { type: "sign_out" }),
        );
      }
      return;
    }
    if (operationVersion.current !== version) {
      return;
    }
    const authority = refreshResult.data;
    if (authority === undefined || authority.must_change_password) {
      setState((current) =>
        transitionSession(current, { type: "sign_out" }),
      );
      return;
    }
    const identityResult = await readCurrentUser({
      auth: authority.access_token,
    });
    if (operationVersion.current !== version) {
      return;
    }
    if (identityResult.data === undefined) {
      setState((current) =>
        transitionSession(current, { type: "sign_out" }),
      );
      return;
    }
    setState((current) =>
      transitionSession(current, {
        type: "authenticate",
        accessToken: authority.access_token,
        principal: identityResult.data,
      }),
    );
  }, []);

  useEffect(() => {
    if (restoreOnMount) {
      void restoreSession();
    }
  }, [restoreOnMount, restoreSession]);

  const logout = useCallback(async () => {
    operationVersion.current += 1;
    setState((current) =>
      transitionSession(current, { type: "sign_out" }),
    );
    try {
      await generatedLogout();
    } finally {
      setState((current) =>
        transitionSession(current, { type: "sign_out" }),
      );
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
