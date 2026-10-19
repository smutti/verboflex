import {
  createContext,
  useContext,
  useEffect,
  useRef,
  useState,
  type PropsWithChildren,
} from "react";

import {
  changePassword as generatedChangePassword,
  logout as generatedLogout,
  issueToken,
  readCurrentUser,
  type AccessTokenResponse,
  type CurrentUserResponse,
} from "../../api/client";
import { client } from "../../api/client/client.gen";
import {
  installSessionRenewal,
  refreshSessionCookie,
  requiresPasswordChange,
} from "./sessionRenewal";

export type SessionState =
  | { status: "checking_session" }
  | { status: "session_unavailable" }
  | { status: "signed_out" }
  | { status: "password_change_required"; accessToken: string }
  | {
      status: "authenticated";
      accessToken: string;
      principal: CurrentUserResponse;
    };

export type SessionEvent =
  | { type: "check_session" }
  | { type: "session_unavailable" }
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
    case "session_unavailable":
      return { status: "session_unavailable" };
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

export function initialSessionState(restoreOnMount: boolean): SessionState {
  return restoreOnMount
    ? { status: "checking_session" }
    : { status: "signed_out" };
}

export interface SessionProviderProps extends PropsWithChildren {
  restoreOnMount?: boolean;
}

export function SessionProvider({
  children,
  restoreOnMount = true,
}: SessionProviderProps) {
  const [state, setState] = useState<SessionState>(() =>
    initialSessionState(restoreOnMount),
  );
  const activeOperation = useRef(Symbol());
  const renewal = useRef<ReturnType<typeof installSessionRenewal> | null>(null);

  function clearSession(event: SessionEvent = { type: "sign_out" }) {
    activeOperation.current = Symbol();
    renewal.current?.dispose();
    renewal.current = null;
    setState((current) => transitionSession(current, event));
  }

  function authenticate(
    authority: AccessTokenResponse,
    principal: CurrentUserResponse,
    operation: symbol,
  ) {
    if (!authority.access_token) {
      clearSession({ type: "session_unavailable" });
      return;
    }
    if (principal.must_change_password) {
      clearSession({ type: "restrict", accessToken: authority.access_token });
      return;
    }
    renewal.current?.dispose();
    renewal.current = installSessionRenewal({
      authority,
      principal,
      isCurrent: () => activeOperation.current === operation,
      onInvalid: () => clearSession(),
      onRestricted: (accessToken) =>
        clearSession({ type: "restrict", accessToken }),
      onPrincipal: (updatedPrincipal) => {
        setState((current) =>
          current.status === "authenticated"
            ? { ...current, principal: updatedPrincipal }
            : current,
        );
      },
    });
    setState((current) =>
      transitionSession(current, {
        type: "authenticate",
        accessToken: authority.access_token,
        principal,
      }),
    );
  }

  useEffect(() => {
    if (state.status !== "password_change_required") {
      return;
    }
    const accessToken = state.accessToken;
    const operation = activeOperation.current;
    let mounted = true;
    const interceptor = client.interceptors.response.use(
      (response, request) => {
        if (request.headers.get("Authorization") !== `Bearer ${accessToken}`) {
          return response;
        }
        const event: SessionEvent | null =
          response.status === 401 ? { type: "sign_out" } : null;
        // A delayed response from a previous login must not revoke newer authority.
        if (event && mounted && activeOperation.current === operation) {
          activeOperation.current = Symbol();
          setState((current) => transitionSession(current, event));
        }
        return response;
      },
    );
    return () => {
      mounted = false;
      client.interceptors.response.eject(interceptor);
    };
  }, [state]);

  async function login(credentials: LoginCredentials) {
    const operation = Symbol();
    activeOperation.current = operation;
    renewal.current?.dispose();
    renewal.current = null;
    const tokenResult = await issueToken({
      body: {
        username: credentials.email,
        password: credentials.password,
      },
    });
    if (activeOperation.current !== operation) {
      return;
    }
    const authority = tokenResult.data;
    if (authority === undefined) {
      setState((current) => transitionSession(current, { type: "sign_out" }));
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
    if (activeOperation.current !== operation) {
      return;
    }
    if (identityResult.data === undefined) {
      setState((current) => transitionSession(current, { type: "sign_out" }));
      return;
    }
    authenticate(authority, identityResult.data, operation);
  }

  async function changePassword(passwords: PasswordChange) {
    if (
      state.status !== "password_change_required" &&
      state.status !== "authenticated"
    ) {
      return;
    }
    const accessToken = state.accessToken;
    const operation = activeOperation.current;
    const result = await generatedChangePassword({
      auth: accessToken,
      body: {
        current_password: passwords.currentPassword,
        new_password: passwords.newPassword,
      },
    });
    if (activeOperation.current !== operation) {
      return;
    }
    if (result.error !== undefined) {
      throw new Error("Session action failed");
    }
    clearSession();
  }

  async function restoreSession() {
    if (renewal.current) {
      // A retry during an existing session preserves editors and navigation.
      await renewal.current.renew().catch(() => undefined);
      return;
    }
    const operation = Symbol();
    activeOperation.current = operation;
    setState((current) =>
      transitionSession(current, { type: "check_session" }),
    );
    try {
      const refreshResult = await refreshSessionCookie();
      if (activeOperation.current !== operation) return;
      const authority = refreshResult.data;
      if (authority === undefined) {
        setState((current) =>
          transitionSession(current, {
            type:
              refreshResult.response?.status === 401
                ? "sign_out"
                : "session_unavailable",
          }),
        );
        return;
      }
      if (authority.must_change_password) {
        clearSession({ type: "restrict", accessToken: authority.access_token });
        return;
      }
      const identityResult = await readCurrentUser({
        auth: authority.access_token,
      });
      if (activeOperation.current !== operation) return;
      if (identityResult.data === undefined) {
        if (
          identityResult.response?.status === 403 &&
          requiresPasswordChange(identityResult.error)
        ) {
          clearSession({
            type: "restrict",
            accessToken: authority.access_token,
          });
        } else {
          setState((current) =>
            transitionSession(current, {
              type:
                identityResult.response?.status === 401
                  ? "sign_out"
                  : "session_unavailable",
            }),
          );
        }
        return;
      }
      authenticate(authority, identityResult.data, operation);
    } catch {
      if (activeOperation.current === operation) {
        setState((current) =>
          transitionSession(current, { type: "session_unavailable" }),
        );
      }
    }
  }

  const restoreSessionRef = useRef(restoreSession);

  useEffect(() => {
    if (restoreOnMount) {
      void restoreSessionRef.current();
    }
    return () => {
      activeOperation.current = Symbol();
      renewal.current?.dispose();
      renewal.current = null;
    };
  }, [restoreOnMount]);

  async function logout() {
    clearSession();
    await generatedLogout();
  }

  const value: SessionValue = {
    state,
    login,
    changePassword,
    restoreSession,
    logout,
  };

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
